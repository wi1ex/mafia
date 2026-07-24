from __future__ import annotations
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import UUID, uuid4
import structlog
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.global_chat import (
    GlobalChatMessage,
    GlobalChatMessageReaction,
    GlobalChatReactionAlert,
    GlobalChatReadState,
)
from ..models.sanction import UserSanction
from ..models.user import User
from ..core.db import SessionLocal
from ..core.roles import (
    ROLE_ADMIN,
    ROLE_MODER,
    can_moderate_chat_message,
    can_purge_deleted_chat_message,
    can_view_deleted_chat_message,
    is_chat_moderator_role,
    normalize_user_role,
)
from ..realtime.sio import sio
from ..security.parameters import get_cached_settings
from ..api.utils import is_user_in_active_game
from ..services.blacklist import filter_notification_targets_for_actor, is_user_blacklisted_by
from ..services.minio import (
    CHAT_IMAGE_PENDING_SEGMENT,
    CHAT_IMAGE_PREFIX,
    delete_object_async,
    validate_chat_image_object_async,
)
from ..services.user_cache import get_user_profiles_cached

log = structlog.get_logger()

GLOBAL_CHAT_ROOM = "global_chat:open"
GLOBAL_CHAT_OPEN_USER_ROOM_PREFIX = "global_chat:user_open"
GLOBAL_CHAT_HISTORY_LIMIT = 100
GLOBAL_CHAT_CONTEXT_WINDOW = 25
GLOBAL_CHAT_MAX_TEXT_LEN = 1000
GLOBAL_CHAT_ADMIN_USERNAME = "admin"
GLOBAL_CHAT_IMAGE_KEY_RE = re.compile(r"^[a-zA-Z0-9._/-]{3,256}$")
GLOBAL_CHAT_MENTION_RE = re.compile(r"(?<!\S)@([a-zA-Zа-яА-ЯёЁ0-9._\-()]{2,20})(?![a-zA-Zа-яА-ЯёЁ0-9._\-()])")
SANCTION_RULE_POINT_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)*)\.")
GLOBAL_CHAT_REACTIONS_ALLOWLIST: tuple[str, ...] = (
    "👍🏼",
    "👎🏼",
    "🔥",
    "❤️",
    "😎",
    "😂",
    "🤯",
    "😭",
    "😡",
    "🤮",
    "🤡",
    "🎉",
)

SANCTION_TIMEOUT = "timeout"
SANCTION_BAN = "ban"
SANCTION_SUSPEND = "suspend"


@dataclass(frozen=True)
class GlobalChatPermissions:
    can_open: bool
    can_send: bool
    can_react: bool
    can_delete_own: bool
    timeout_active: bool
    ban_active: bool
    in_active_game_as_player: bool
    telegram_verified: bool
    error: str | None = None


def _positive_int(raw: object) -> int:
    try:
        value = int(raw)
    except Exception:
        return 0

    return value if value > 0 else 0


def _normalize_positive_int_list(raw: object) -> list[int]:
    if not isinstance(raw, (list, tuple, set)):
        return []

    seen: set[int] = set()
    out: list[int] = []
    for item in raw:
        value = _positive_int(item)
        if value <= 0 or value in seen:
            continue
        seen.add(value)
        out.append(value)
    out.sort()
    return out


def _normalize_limit(raw: object, *, default: int = GLOBAL_CHAT_HISTORY_LIMIT, max_value: int = GLOBAL_CHAT_HISTORY_LIMIT) -> int:
    value = _positive_int(raw)
    if value <= 0:
        return int(default)

    return min(value, max_value)


def _sanitize_text(raw: object) -> str:
    text = str(raw or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if len(text) > GLOBAL_CHAT_MAX_TEXT_LEN:
        raise ValueError("message_too_long")

    return text


def _username_for(profile: dict[str, Any] | None, user_id: int) -> str:
    username = str((profile or {}).get("username") or "").strip()
    return username or f"user{int(user_id)}"


def _profile_deleted(profile: dict[str, Any] | None) -> bool:
    if not profile:
        return False

    if profile.get("deleted_at"):
        return True

    return str(profile.get("username") or "").strip().lower().startswith("deleted_")


def _extract_mentioned_usernames(text: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for match in GLOBAL_CHAT_MENTION_RE.finditer(str(text or "")):
        username = str(match.group(1) or "").strip()
        if not username:
            continue
        username_key = username.lower()
        if username_key in seen:
            continue
        seen.add(username_key)
        ordered.append(username)
    return ordered


def _extract_mention_matches(text: str) -> list[dict[str, int | str]]:
    matches: list[dict[str, int | str]] = []
    for match in GLOBAL_CHAT_MENTION_RE.finditer(str(text or "")):
        username = str(match.group(1) or "").strip()
        if not username:
            continue
        start = int(match.start())
        end = int(match.end())
        if start < 0 or end <= start:
            continue
        matches.append(
            {
                "username": username,
                "start": start,
                "end": end,
            }
        )
    return matches


async def _resolve_mentioned_users(session: AsyncSession, usernames: set[str]) -> dict[str, dict[str, Any]]:
    if not usernames:
        return {}

    normalized = {str(username or "").strip().lower() for username in usernames if str(username or "").strip()}
    if not normalized:
        return {}

    rows = await session.execute(
        select(User.id, User.username, User.avatar_name, User.role)
        .where(
            User.deleted_at.is_(None),
            func.lower(User.username).in_(normalized),
        )
    )
    resolved: dict[str, dict[str, Any]] = {}
    for user_id_raw, username_raw, avatar_name_raw, role_raw in rows.all():
        user_id = _positive_int(user_id_raw)
        username = str(username_raw or "").strip()
        if user_id <= 0 or not username:
            continue
        resolved[username.lower()] = {
            "id": user_id,
            "username": username,
            "avatar_name": str(avatar_name_raw) if avatar_name_raw else None,
            "role": normalize_user_role(role_raw),
            "deleted": False,
        }
    return resolved


def _mention_span_is_silent(raw: object) -> bool:
    if not isinstance(raw, dict):
        return False

    value = raw.get("silent")
    if isinstance(value, bool):
        return value

    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _build_mention_spans(text: str, resolved_users: dict[str, dict[str, Any]], *, silent_user_ids: Sequence[int] | None = None) -> list[dict[str, Any]]:
    silent_ids = {user_id for user_id in (_positive_int(item) for item in (silent_user_ids or ())) if user_id > 0}
    spans: list[dict[str, Any]] = []
    for match in _extract_mention_matches(text):
        username = str(match.get("username") or "").strip()
        mention = resolved_users.get(username.lower())
        mention_user_id = _positive_int((mention or {}).get("id"))
        if mention_user_id <= 0:
            continue
        start = _positive_int(match.get("start"))
        end = _positive_int(match.get("end"))
        if end <= start:
            continue
        span: dict[str, Any] = {
            "user_id": mention_user_id,
            "start": start,
            "end": end,
        }
        if mention_user_id in silent_ids:
            span["silent"] = True
        spans.append(span)

    return spans


def _normalize_mention_spans(raw: object, *, text_len: int | None = None) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    prepared: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        user_id = _positive_int(item.get("user_id"))
        try:
            start = int(item.get("start"))
            end = int(item.get("end"))
        except Exception:
            continue
        if user_id <= 0 or start < 0 or end <= start:
            continue
        if text_len is not None and (start >= text_len or end > text_len):
            continue
        normalized_item: dict[str, Any] = {
            "user_id": user_id,
            "start": start,
            "end": end,
        }
        if _mention_span_is_silent(item):
            normalized_item["silent"] = True
        prepared.append(normalized_item)

    prepared.sort(key=lambda item: (item["start"], item["end"], item["user_id"]))
    out: list[dict[str, Any]] = []
    last_end = -1
    for item in prepared:
        if item["start"] < last_end:
            continue
        normalized_item: dict[str, Any] = {
            "user_id": item["user_id"],
            "start": item["start"],
            "end": item["end"],
        }
        if _mention_span_is_silent(item):
            normalized_item["silent"] = True
        out.append(normalized_item)
        last_end = item["end"]
    return out


def _mentioned_user_ids_from_spans(mention_spans: Sequence[dict[str, Any]], *, include_silent: bool = True) -> set[int]:
    return {
        user_id
        for mention in mention_spans
        if include_silent or not _mention_span_is_silent(mention)
        for user_id in (_positive_int(mention.get("user_id")),)
        if user_id > 0
    }


def _mention_spans_include_username(text: str, mention_spans: Sequence[dict[str, Any]], username: str) -> bool:
    source = str(text or "")
    target = f"@{str(username or '').strip()}".casefold()
    if target == "@":
        return False

    for mention in mention_spans:
        if _mention_span_is_silent(mention):
            continue
        try:
            start = int(mention.get("start"))
            end = int(mention.get("end"))
        except Exception:
            continue
        if 0 <= start < end <= len(source) and source[start:end].casefold() == target:
            return True

    return False


def _build_mentions_payload_from_spans(mention_spans: Sequence[dict[str, Any]], profiles: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    mentions: list[dict[str, Any]] = []
    seen_user_ids: set[int] = set()
    for mention in mention_spans:
        user_id = _positive_int(mention.get("user_id"))
        if user_id <= 0 or user_id in seen_user_ids:
            continue
        profile = profiles.get(user_id) or {}
        username = str(profile.get("username") or "").strip()
        if not username:
            continue
        seen_user_ids.add(user_id)
        mentions.append(
            {
                "id": user_id,
                "username": username,
                "avatar_name": profile.get("avatar_name"),
                "role": normalize_user_role(profile.get("role")),
                "theme_color": profile.get("theme_color"),
                "theme_icon": profile.get("theme_icon"),
                "deleted": _profile_deleted(profile),
            }
        )
    return mentions


def _render_text_with_mention_spans(text: str, mention_spans: Sequence[dict[str, Any]], profiles: dict[int, dict[str, Any]]) -> str:
    source = str(text or "")
    spans = _normalize_mention_spans(list(mention_spans), text_len=len(source))
    if not spans:
        return source

    chunks: list[str] = []
    last_index = 0
    for mention in spans:
        start = mention["start"]
        end = mention["end"]
        user_id = mention["user_id"]
        if start < last_index:
            continue
        profile = profiles.get(user_id) or {}
        username = str(profile.get("username") or "").strip()
        replacement = f"@{username}" if username else source[start:end]
        chunks.append(source[last_index:start])
        chunks.append(replacement)
        last_index = end

    if last_index == 0:
        return source

    chunks.append(source[last_index:])
    return "".join(chunks)


def _build_mentions_payload(text: str, resolved_users: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    mentions: list[dict[str, Any]] = []
    for username in _extract_mentioned_usernames(text):
        mention = resolved_users.get(username.lower())
        if mention is None:
            continue
        mentions.append(
            {
                "id": int(mention["id"]),
                "username": str(mention["username"]),
                "avatar_name": mention.get("avatar_name"),
                "role": normalize_user_role(mention.get("role")),
                "theme_color": mention.get("theme_color"),
                "theme_icon": mention.get("theme_icon"),
                "deleted": bool(mention.get("deleted")),
            }
        )
    return mentions


def _build_mentioned_user_ids(text: str, resolved_users: dict[str, dict[str, Any]]) -> set[int]:
    mentioned_user_ids: set[int] = set()
    for username in _extract_mentioned_usernames(text):
        mention = resolved_users.get(username.lower())
        mention_user_id = _positive_int((mention or {}).get("id"))
        if mention_user_id > 0:
            mentioned_user_ids.add(mention_user_id)
    return mentioned_user_ids


def _collect_message_mention_context(messages: Sequence[GlobalChatMessage], *, include_deleted: bool = False) -> tuple[dict[int, list[dict[str, Any]]], set[int], set[str]]:
    mention_spans_by_message_id: dict[int, list[dict[str, Any]]] = {}
    mention_user_ids: set[int] = set()
    mentioned_usernames: set[str] = set()
    for message in messages:
        if not include_deleted and message.deleted_at is not None:
            continue
        message_id = _positive_int(message.id)
        text_value = str(message.text or "")
        spans = _normalize_mention_spans(getattr(message, "mention_spans", None), text_len=len(text_value))
        if spans:
            if message_id > 0:
                mention_spans_by_message_id[message_id] = spans
            mention_user_ids.update(_mentioned_user_ids_from_spans(spans))
            continue
        mentioned_usernames.update(_extract_mentioned_usernames(text_value))
    return mention_spans_by_message_id, mention_user_ids, mentioned_usernames


def _reply_snippet(text: str, *, has_image: bool) -> str:
    source = " ".join(str(text or "").split())
    if not source:
        return "Изображение" if has_image else ""

    if len(source) <= 80:
        return source

    return source[:77].rstrip() + "..."


def _truncate_text(value: str, max_len: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= max_len:
        return text

    return text[: max(0, max_len - 3)].rstrip() + "..."


def _extract_sanction_rule_point(reason: str) -> str | None:
    match = SANCTION_RULE_POINT_RE.match(str(reason or ""))
    if not match:
        return None

    value = str(match.group(1) or "").strip(". ").strip()
    return value or None


def _format_sanction_reason_details(reason: str) -> str:
    point = _extract_sanction_rule_point(reason)
    if point:
        return f" (пункт правил: {point})"

    normalized_reason = _truncate_text(reason, 140)
    if normalized_reason:
        return f" (причина: {normalized_reason})"

    return ""


def _sanction_kind_label(kind: str) -> str:
    value = str(kind or "").strip().lower()
    if value == SANCTION_TIMEOUT:
        return "таймаут"

    if value == SANCTION_BAN:
        return "бан"

    if value == SANCTION_SUSPEND:
        return "отстранение от игр"

    return "санкцию"


async def _resolve_global_chat_notice_author_user_id(session: AsyncSession, *, preferred_user_id: int | None = None) -> int | None:
    preferred_id = _positive_int(preferred_user_id)
    preferred_user: User | None = None
    if preferred_id > 0:
        preferred_user = await session.get(User, preferred_id)
        if preferred_user and preferred_user.deleted_at is None and str(preferred_user.role or "").strip().lower() == "admin":
            return int(preferred_user.id)

    admin_id = await session.scalar(
        select(User.id)
        .where(
            User.deleted_at.is_(None),
            User.role == "admin",
        )
        .order_by(User.id.asc())
        .limit(1)
    )
    if admin_id is not None:
        return int(admin_id)

    if preferred_user and preferred_user.deleted_at is None:
        return int(preferred_user.id)

    return None


async def _resolve_chat_notice_target_username(session: AsyncSession, *, user_id: int, username: str | None = None) -> str:
    normalized_user_id = _positive_int(user_id)
    normalized_username = str(username or "").strip()
    if normalized_username:
        return normalized_username

    if normalized_user_id <= 0:
        return "user0"

    profiles = await get_user_profiles_cached(session, {normalized_user_id})
    return _username_for(profiles.get(normalized_user_id), normalized_user_id)


def _format_chat_notice_target_mention(target_username: str) -> str:
    normalized_username = str(target_username or "").strip().lstrip("@").strip()
    if not normalized_username:
        return target_username

    return f"@{normalized_username}"


def build_global_chat_sanction_issued_text(*, target_username: str, kind: str, reason: str, duration_label: str | None = None) -> str:
    kind_value = str(kind or "").strip().lower()
    target_mention = _format_chat_notice_target_mention(target_username)
    details = _format_sanction_reason_details(reason)
    duration = str(duration_label or "").strip()
    if kind_value == SANCTION_SUSPEND:
        base = f"Пользователь {target_mention} отстранен от игр"
        if duration:
            base += f" на {duration}"
        return f"{base}{details}"

    if kind_value == SANCTION_TIMEOUT:
        base = f"Пользователь {target_mention} получил таймаут"
        if duration:
            base += f" на {duration}"
        return f"{base}{details}"

    if kind_value == SANCTION_BAN:
        return f"Пользователь {target_mention} был забанен{details}"

    base = f"Пользователь {target_mention} получил {_sanction_kind_label(kind)}"
    if duration:
        base += f" на {duration}"
    return f"{base}{details}"


def build_global_chat_sanction_removed_text(*, target_username: str, kind: str, reason: str, source: str, remaining_duration_label: str | None = None) -> str:
    source_value = str(source or "").strip().lower()
    kind_value = str(kind or "").strip().lower()
    target_mention = _format_chat_notice_target_mention(target_username)
    if source_value == "expired":
        if kind_value == SANCTION_TIMEOUT:
            return f"У пользователя {target_mention} истек срок таймаута"

        if kind_value == SANCTION_SUSPEND:
            return f"У пользователя {target_mention} истек срок отстранения от игр"

        return f"У пользователя {target_mention} истек срок {_sanction_kind_label(kind)}"

    if source_value == "game":
        if kind_value == SANCTION_SUSPEND:
            return f"У пользователя {target_mention} истек срок отстранения от игр (после проведенной игры)"

        return f"У пользователя {target_mention} истек срок {_sanction_kind_label(kind)} (после проведенной игры)"

    remaining = str(remaining_duration_label or "").strip()
    remaining_suffix = f" (раньше срока на {remaining})" if remaining else ""
    if kind_value == SANCTION_TIMEOUT:
        return f"У пользователя {target_mention} досрочно снят таймаут{remaining_suffix}"

    if kind_value == SANCTION_SUSPEND:
        return f"У пользователя {target_mention} досрочно снято отстранение от игр{remaining_suffix}"

    if kind_value == SANCTION_BAN:
        return f"Пользователь {target_mention} разбанен"

    return f"У пользователя {target_mention} снята {_sanction_kind_label(kind)}"


def build_global_chat_sanction_adjusted_text(*, target_username: str, kind: str, action: str, duration_label: str, remaining_duration_label: str | None = None) -> str:
    kind_value = str(kind or "").strip().lower()
    action_value = str(action or "").strip().lower()
    target_mention = _format_chat_notice_target_mention(target_username)
    duration = str(duration_label or "").strip()
    direction = "увеличен" if action_value == "increase" else "уменьшен"

    if kind_value == SANCTION_TIMEOUT:
        base = f"У пользователя {target_mention} {direction} срок таймаута"
    elif kind_value == SANCTION_SUSPEND:
        base = f"У пользователя {target_mention} {direction} срок отстранения от игр"
    else:
        base = f"У пользователя {target_mention} {direction} срок {_sanction_kind_label(kind)}"

    if duration:
        base += f" на {duration}"

    remaining = str(remaining_duration_label or "").strip()
    if remaining:
        base += f". До окончания осталось {remaining}"

    return base


def build_global_chat_role_changed_text(*, target_username: str, role: str, granted: bool) -> str:
    role_value = str(role or "").strip().lower()
    target_mention = _format_chat_notice_target_mention(target_username)

    if role_value == "moder":
        if granted:
            return f"Пользователю {target_mention} выдана роль Модератор"
        return f"У пользователя {target_mention} снята роль Модератор"

    role_label = role_value or "role"
    if granted:
        return f"Пользователю {target_mention} выдана роль {role_label}"
    return f"У пользователя {target_mention} снята роль {role_label}"


def build_global_chat_nickname_reset_text(*, previous_username: str, new_username: str) -> str:
    previous_mention = _format_chat_notice_target_mention(previous_username)
    return (
        f"У пользователя {previous_mention} сброшен никнейм (пункт правил: 4.5.1)"
    )


def build_global_chat_avatar_deleted_text(*, target_username: str) -> str:
    target_mention = _format_chat_notice_target_mention(target_username)
    return f"У пользователя {target_mention} удален аватар (пункт правил: 4.5.1)"


def _message_public_dict(message: GlobalChatMessage) -> dict[str, Any]:
    deleted = message.deleted_at is not None
    return {
        "id": int(message.id),
        "created_at": message.created_at,
        "deleted": deleted,
        "deleted_at": message.deleted_at,
        "deleted_content_available": deleted and (bool(str(message.text or "").strip()) or bool(message.image_object_key)),
        "text": "" if deleted else str(message.text or ""),
        "user_id": int(message.user_id),
        "reply_to_message_id": _positive_int(message.reply_to_message_id) or None,
        "image_object_key": None if deleted else (str(message.image_object_key) if message.image_object_key else None),
    }


async def _fetch_active_sanctions(session: AsyncSession, user_id: int) -> dict[str, UserSanction | None]:
    now = datetime.now(timezone.utc)
    rows = await session.execute(
        select(UserSanction)
        .where(
            UserSanction.user_id == int(user_id),
            UserSanction.revoked_at.is_(None),
            or_(UserSanction.expires_at.is_(None), UserSanction.expires_at > now),
        )
        .order_by(UserSanction.issued_at.desc(), UserSanction.id.desc())
    )
    items = rows.scalars().all()
    out = {
        SANCTION_TIMEOUT: None,
        SANCTION_BAN: None,
        SANCTION_SUSPEND: None,
    }
    for row in items:
        if row.kind in out and out[row.kind] is None:
            out[row.kind] = row
    return out


async def resolve_global_chat_permissions(session: AsyncSession, user_id: int) -> GlobalChatPermissions:
    user = await session.get(User, int(user_id))
    if not user or user.deleted_at is not None:
        return GlobalChatPermissions(
            can_open=False,
            can_send=False,
            can_react=False,
            can_delete_own=False,
            timeout_active=False,
            ban_active=False,
            in_active_game_as_player=False,
            telegram_verified=False,
            error="unauthorized",
        )

    sanctions = await _fetch_active_sanctions(session, int(user.id))
    timeout_active = sanctions.get(SANCTION_TIMEOUT) is not None
    ban_active = sanctions.get(SANCTION_BAN) is not None
    telegram_verified = bool(user.telegram_id)
    try:
        in_active_game_as_player = await is_user_in_active_game(int(user.id), strict=True, scan_if_missing=True)
    except RuntimeError:
        return GlobalChatPermissions(
            can_open=False,
            can_send=False,
            can_react=False,
            can_delete_own=False,
            timeout_active=timeout_active,
            ban_active=ban_active,
            in_active_game_as_player=False,
            telegram_verified=telegram_verified,
            error="presence_unavailable",
        )

    app_settings = get_cached_settings()
    is_admin = normalize_user_role(user.role) == ROLE_ADMIN
    can_open = True
    error: str | None = None
    if not app_settings.chat_open_enabled and not is_admin:
        can_open = False
        error = "chat_disabled"
    elif ban_active:
        can_open = False
        error = "user_banned"
    elif timeout_active:
        can_open = False
        error = "user_timeout"
    elif in_active_game_as_player:
        can_open = False
        error = "active_game_player"
    elif get_cached_settings().verification_restrictions and not telegram_verified:
        can_open = False
        error = "not_verified"

    can_send = can_open and (is_admin or bool(app_settings.chat_messages_enabled))
    can_react = can_open
    can_delete_own = can_open

    return GlobalChatPermissions(
        can_open=can_open,
        can_send=can_send,
        can_react=can_react,
        can_delete_own=can_delete_own,
        timeout_active=timeout_active,
        ban_active=ban_active,
        in_active_game_as_player=in_active_game_as_player,
        telegram_verified=telegram_verified,
        error=error,
    )


def permissions_payload(permissions: GlobalChatPermissions) -> dict[str, bool]:
    return {
        "can_open": permissions.can_open,
        "can_send": permissions.can_send,
        "can_react": permissions.can_react,
        "can_delete_own": permissions.can_delete_own,
    }


def global_chat_send_error(permissions: GlobalChatPermissions) -> str:
    if permissions.ban_active:
        return "user_banned"

    if permissions.timeout_active:
        return "user_timeout"

    if not permissions.can_open:
        return permissions.error or "forbidden"

    if not permissions.can_send and not bool(get_cached_settings().chat_messages_enabled):
        return "chat_messages_disabled"

    return "forbidden"


def _should_force_close(permissions: GlobalChatPermissions) -> bool:
    if permissions.can_open:
        return False

    return permissions.error in {"active_game_player", "chat_disabled", "not_verified", "unauthorized", "user_timeout", "user_banned"}


def global_chat_open_user_room(user_id: int) -> str:
    return f"{GLOBAL_CHAT_OPEN_USER_ROOM_PREFIX}:{int(user_id)}"


def is_global_chat_open_for_user(user_id: int) -> bool:
    uid = _positive_int(user_id)
    if uid <= 0:
        return False

    try:
        return next(sio.manager.get_participants("/chat", global_chat_open_user_room(uid)), None) is not None

    except Exception:
        return False


async def _get_latest_global_chat_message_id(session: AsyncSession) -> int:
    latest_message_id = await session.scalar(select(func.max(GlobalChatMessage.id)))
    return _positive_int(latest_message_id)


def _alert_sort_value(raw: object) -> float:
    if not isinstance(raw, datetime):
        return 0.0

    value = raw
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


async def _ensure_global_chat_read_state(session: AsyncSession, *, user_id: int) -> GlobalChatReadState | None:
    uid = _positive_int(user_id)
    if uid <= 0:
        return None

    row = await session.get(GlobalChatReadState, uid)
    if row is not None:
        updated = False
        current_alert_read_message_id = _positive_int(getattr(row, "last_read_alert_message_id", None))
        if current_alert_read_message_id <= 0:
            fallback_alert_read_message_id = _positive_int(row.last_seen_message_id)
            if fallback_alert_read_message_id <= 0:
                fallback_alert_read_message_id = await _get_latest_global_chat_message_id(session)
            row.last_read_alert_message_id = fallback_alert_read_message_id or None
            current_alert_read_message_id = _positive_int(row.last_read_alert_message_id)
            updated = True
        current_read_alert_message_ids = _normalize_positive_int_list(getattr(row, "read_alert_message_ids", None))
        sanitized_read_alert_message_ids = [
            message_id
            for message_id in current_read_alert_message_ids
            if message_id > current_alert_read_message_id
        ]
        if getattr(row, "read_alert_message_ids", None) is None or sanitized_read_alert_message_ids != current_read_alert_message_ids:
            row.read_alert_message_ids = sanitized_read_alert_message_ids
            updated = True
        if updated:
            row.updated_at = datetime.now(timezone.utc)
            await session.commit()
        return row

    latest_message_id = await _get_latest_global_chat_message_id(session)
    row = GlobalChatReadState(
        user_id=uid,
        last_seen_message_id=latest_message_id or None,
        last_read_alert_message_id=latest_message_id or None,
        read_alert_message_ids=[],
        updated_at=datetime.now(timezone.utc),
    )
    session.add(row)
    await session.commit()
    return row


async def mark_global_chat_seen(session: AsyncSession, *, user_id: int, message_id: int | None = None) -> int:
    uid = _positive_int(user_id)
    if uid <= 0:
        return 0

    row = await _ensure_global_chat_read_state(session, user_id=uid)
    if row is None:
        return 0

    seen_message_id = _positive_int(message_id)
    if seen_message_id <= 0:
        seen_message_id = await _get_latest_global_chat_message_id(session)

    current_seen_message_id = _positive_int(row.last_seen_message_id)
    if seen_message_id > current_seen_message_id:
        row.last_seen_message_id = seen_message_id
    row.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return max(current_seen_message_id, seen_message_id)


async def _build_global_chat_alert_user_ids_map(session: AsyncSession, messages: Sequence[GlobalChatMessage]) -> dict[int, set[int]]:
    if not messages:
        return {}

    reply_ids = {
        _positive_int(message.reply_to_message_id)
        for message in messages
        if _positive_int(message.reply_to_message_id) > 0
    }
    reply_author_ids: dict[int, int] = {}
    if reply_ids:
        reply_rows = await session.execute(
            select(GlobalChatMessage.id, GlobalChatMessage.user_id)
            .where(GlobalChatMessage.id.in_(reply_ids))
        )
        for reply_message_id_raw, reply_user_id_raw in reply_rows.all():
            reply_message_id = _positive_int(reply_message_id_raw)
            reply_user_id = _positive_int(reply_user_id_raw)
            if reply_message_id > 0 and reply_user_id > 0:
                reply_author_ids[reply_message_id] = reply_user_id

    mention_spans_by_message_id, _, mentioned_usernames = _collect_message_mention_context(messages)
    resolved_mentions = await _resolve_mentioned_users(session, mentioned_usernames)
    moderator_user_ids: set[int] | None = None

    out: dict[int, set[int]] = {}
    for message in messages:
        message_id = _positive_int(message.id)
        if message_id <= 0:
            continue

        alert_user_ids: set[int] = set()
        reply_to_message_id = _positive_int(message.reply_to_message_id)
        if reply_to_message_id > 0:
            reply_author_id = _positive_int(reply_author_ids.get(reply_to_message_id))
            if reply_author_id > 0:
                alert_user_ids.add(reply_author_id)

        mention_spans = mention_spans_by_message_id.get(message_id) or []
        if mention_spans:
            alert_user_ids.update(_mentioned_user_ids_from_spans(mention_spans, include_silent=False))
            mentions_admin = _mention_spans_include_username(
                str(message.text or ""),
                mention_spans,
                GLOBAL_CHAT_ADMIN_USERNAME,
            )
        else:
            alert_user_ids.update(_build_mentioned_user_ids(str(message.text or ""), resolved_mentions))
            mentions_admin = (
                GLOBAL_CHAT_ADMIN_USERNAME in resolved_mentions
                and GLOBAL_CHAT_ADMIN_USERNAME in {
                    username.casefold()
                    for username in _extract_mentioned_usernames(str(message.text or ""))
                }
            )

        if mentions_admin:
            if moderator_user_ids is None:
                moderator_rows = await session.execute(
                    select(User.id).where(
                        User.deleted_at.is_(None),
                        func.lower(User.role) == ROLE_MODER,
                    )
                )
                moderator_user_ids = {
                    user_id
                    for user_id in (
                        _positive_int(raw_user_id)
                        for raw_user_id in moderator_rows.scalars().all()
                    )
                    if user_id > 0
                }
            alert_user_ids.update(moderator_user_ids)

        author_user_id = _positive_int(message.user_id)
        if author_user_id > 0:
            alert_user_ids.discard(author_user_id)
            if alert_user_ids:
                alert_user_ids = set(
                    await filter_notification_targets_for_actor(
                        session,
                        actor_id=author_user_id,
                        target_ids=alert_user_ids,
                    )
                )

        out[message_id] = alert_user_ids

    return out


async def get_global_chat_alert_user_ids(session: AsyncSession, *, message_id: int) -> set[int]:
    message = await get_global_chat_message(session, message_id)
    if message is None:
        return set()

    alert_map = await _build_global_chat_alert_user_ids_map(session, [message])
    return set(alert_map.get(int(message.id)) or set())


async def _compact_global_chat_read_alert_state(session: AsyncSession, *, user_id: int, read_state: GlobalChatReadState, additional_read_message_ids: Sequence[int] | None = None) -> None:
    uid = _positive_int(user_id)
    if uid <= 0:
        read_state.read_alert_message_ids = []
        return

    current_alert_read_message_id = _positive_int(read_state.last_read_alert_message_id)
    read_alert_message_ids = {
        message_id
        for message_id in _normalize_positive_int_list(getattr(read_state, "read_alert_message_ids", None))
        if message_id > current_alert_read_message_id
    }
    for raw_message_id in additional_read_message_ids or ():
        message_id = _positive_int(raw_message_id)
        if message_id > current_alert_read_message_id:
            read_alert_message_ids.add(message_id)

    if not read_alert_message_ids:
        read_state.read_alert_message_ids = []
        return

    max_read_alert_message_id = max(read_alert_message_ids)
    rows = await session.execute(
        select(GlobalChatMessage)
        .where(
            GlobalChatMessage.id > current_alert_read_message_id,
            GlobalChatMessage.id <= max_read_alert_message_id,
            GlobalChatMessage.deleted_at.is_(None),
            GlobalChatMessage.user_id != uid,
        )
        .order_by(GlobalChatMessage.id.asc())
    )
    messages = rows.scalars().all()
    if not messages:
        read_state.read_alert_message_ids = []
        return

    alert_map = await _build_global_chat_alert_user_ids_map(session, messages)
    valid_read_alert_message_ids = {
        int(message.id)
        for message in messages
        if int(message.id) in read_alert_message_ids and uid in (alert_map.get(int(message.id)) or set())
    }
    if not valid_read_alert_message_ids:
        read_state.read_alert_message_ids = []
        return

    next_alert_read_message_id = current_alert_read_message_id
    remaining_read_alert_message_ids = set(valid_read_alert_message_ids)
    for message in messages:
        message_id = int(message.id)
        if uid not in (alert_map.get(message_id) or set()):
            continue
        if message_id in remaining_read_alert_message_ids:
            next_alert_read_message_id = message_id
            remaining_read_alert_message_ids.discard(message_id)
            continue
        break

    read_state.last_read_alert_message_id = next_alert_read_message_id or None
    read_state.read_alert_message_ids = sorted(
        message_id
        for message_id in remaining_read_alert_message_ids
        if message_id > next_alert_read_message_id
    )


async def _fetch_global_chat_unread_message_alert_targets(session: AsyncSession, *, user_id: int, read_state: GlobalChatReadState) -> list[tuple[float, int]]:
    uid = _positive_int(user_id)
    if uid <= 0:
        return []

    last_read_alert_message_id = _positive_int(read_state.last_read_alert_message_id)
    read_alert_message_ids = {
        message_id
        for message_id in _normalize_positive_int_list(getattr(read_state, "read_alert_message_ids", None))
        if message_id > last_read_alert_message_id
    }
    rows = await session.execute(
        select(GlobalChatMessage)
        .where(
            GlobalChatMessage.id > last_read_alert_message_id,
            GlobalChatMessage.deleted_at.is_(None),
            GlobalChatMessage.user_id != uid,
        )
        .order_by(GlobalChatMessage.id.asc())
    )
    messages = rows.scalars().all()
    if not messages:
        return []

    alert_map = await _build_global_chat_alert_user_ids_map(session, messages)
    return [
        (_alert_sort_value(message.created_at), int(message.id))
        for message in messages
        if (
            uid in (alert_map.get(int(message.id)) or set())
            and int(message.id) not in read_alert_message_ids
        )
    ]


async def _fetch_global_chat_unread_reaction_alert_targets(session: AsyncSession, *, user_id: int) -> list[tuple[float, int]]:
    uid = _positive_int(user_id)
    if uid <= 0:
        return []

    rows = await session.execute(
        select(
            GlobalChatReactionAlert.message_id,
            GlobalChatReactionAlert.updated_at,
            GlobalChatReactionAlert.created_at,
        )
        .join(GlobalChatMessage, GlobalChatMessage.id == GlobalChatReactionAlert.message_id)
        .where(
            GlobalChatReactionAlert.user_id == uid,
            GlobalChatMessage.user_id == uid,
            GlobalChatMessage.deleted_at.is_(None),
        )
        .order_by(
            GlobalChatReactionAlert.updated_at.asc(),
            GlobalChatReactionAlert.message_id.asc(),
        )
    )

    targets: list[tuple[float, int]] = []
    for message_id_raw, updated_at_raw, created_at_raw in rows.all():
        message_id = _positive_int(message_id_raw)
        if message_id <= 0:
            continue
        sort_value = _alert_sort_value(updated_at_raw) or _alert_sort_value(created_at_raw)
        targets.append((sort_value, message_id))
    return targets


async def fetch_global_chat_unread_target_message_ids(session: AsyncSession, *, user_id: int) -> list[int]:
    uid = _positive_int(user_id)
    if uid <= 0:
        return []

    read_state = await _ensure_global_chat_read_state(session, user_id=uid)
    if read_state is None:
        return []

    targets_by_message_id: dict[int, float] = {}
    targets = await _fetch_global_chat_unread_message_alert_targets(
        session,
        user_id=uid,
        read_state=read_state,
    )
    targets.extend(await _fetch_global_chat_unread_reaction_alert_targets(session, user_id=uid))

    for sort_value, message_id in targets:
        current_sort_value = targets_by_message_id.get(message_id)
        if current_sort_value is None or sort_value > current_sort_value:
            targets_by_message_id[message_id] = sort_value

    return [
        message_id
        for message_id, _ in sorted(
            targets_by_message_id.items(),
            key=lambda item: (item[1], item[0]),
        )
    ]


async def count_global_chat_unread(session: AsyncSession, *, user_id: int) -> int:
    return len(await fetch_global_chat_unread_target_message_ids(session, user_id=user_id))


async def mark_global_chat_alert_read(session: AsyncSession, *, user_id: int, message_id: int) -> bool:
    uid = _positive_int(user_id)
    target_message_id = _positive_int(message_id)
    if uid <= 0 or target_message_id <= 0:
        return False

    read_state = await _ensure_global_chat_read_state(session, user_id=uid)
    if read_state is None:
        return False

    message = await get_global_chat_message(session, target_message_id)
    if message is None or message.deleted_at is not None:
        return False

    reaction_alert = await session.get(
        GlobalChatReactionAlert,
        {
            "user_id": uid,
            "message_id": target_message_id,
        },
    )
    reaction_alert_marked = reaction_alert is not None
    if reaction_alert is not None:
        await session.delete(reaction_alert)

    current_alert_read_message_id = _positive_int(read_state.last_read_alert_message_id)
    if target_message_id <= current_alert_read_message_id:
        read_state.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return True

    alert_user_ids = await get_global_chat_alert_user_ids(session, message_id=target_message_id)
    if uid not in alert_user_ids and not reaction_alert_marked:
        return False

    if uid in alert_user_ids:
        await _compact_global_chat_read_alert_state(
            session,
            user_id=uid,
            read_state=read_state,
            additional_read_message_ids=[target_message_id],
        )
    read_state.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return True


async def mark_global_chat_alert_read_for_open_users(session: AsyncSession, *, message_id: int, user_ids: Sequence[int]) -> tuple[int, ...]:
    target_message_id = _positive_int(message_id)
    if target_message_id <= 0:
        return ()

    open_user_ids = sorted({
        uid
        for uid in (_positive_int(user_id) for user_id in user_ids)
        if uid > 0 and is_global_chat_open_for_user(uid)
    })
    if not open_user_ids:
        return ()

    read_user_ids: list[int] = []
    for uid in open_user_ids:
        if await mark_global_chat_alert_read(session, user_id=uid, message_id=target_message_id):
            read_user_ids.append(uid)
    return tuple(read_user_ids)


async def emit_global_chat_unread_state(
    user_id: int,
    *,
    count: int | None = None,
    target_message_ids: Sequence[int] | None = None,
) -> None:
    uid = _positive_int(user_id)
    if uid <= 0:
        return

    unread_target_message_ids = [
        _positive_int(message_id)
        for message_id in (target_message_ids or [])
        if _positive_int(message_id) > 0
    ]
    unread_count = max(0, int(count or 0)) if count is not None else len(unread_target_message_ids)
    if count is None or target_message_ids is None:
        try:
            async with SessionLocal() as session:
                unread_target_message_ids = await fetch_global_chat_unread_target_message_ids(session, user_id=uid)
                unread_count = len(unread_target_message_ids)
        except Exception:
            log.exception("global_chat.unread_state_emit_failed", user_id=uid)
            return

    await sio.emit(
        "chat_unread_count",
        {"count": unread_count},
        room=f"user:{uid}",
        namespace="/auth",
    )
    await sio.emit(
        "chat_unread_targets",
        {"message_ids": unread_target_message_ids},
        room=global_chat_open_user_room(uid),
        namespace="/chat",
    )


async def emit_global_chat_unread_count(user_id: int, *, count: int | None = None) -> None:
    await emit_global_chat_unread_state(user_id, count=count)


async def emit_global_chat_unread_states(user_ids: Sequence[int]) -> None:
    unique_user_ids = sorted({_positive_int(user_id) for user_id in user_ids if _positive_int(user_id) > 0})
    for uid in unique_user_ids:
        await emit_global_chat_unread_state(uid)


async def emit_global_chat_permissions_updated(user_id: int) -> None:
    uid = _positive_int(user_id)
    if uid <= 0:
        return

    payload: dict[str, Any] = {"refresh": True}
    try:
        async with SessionLocal() as session:
            permissions = await resolve_global_chat_permissions(session, uid)
        payload = {
            "permissions": permissions_payload(permissions),
            "error": permissions.error,
            "force_close": _should_force_close(permissions),
        }
    except Exception:
        payload = {"refresh": True}
    await sio.emit(
        "chat_permissions_updated",
        payload,
        room=global_chat_open_user_room(uid),
        namespace="/chat",
    )


async def emit_global_chat_permissions_refresh() -> None:
    await sio.emit(
        "chat_permissions_updated",
        {"refresh": True},
        room=GLOBAL_CHAT_ROOM,
        namespace="/chat",
    )


async def emit_global_chat_messages_refresh() -> None:
    await sio.emit(
        "chat_refresh_requested",
        {},
        room=GLOBAL_CHAT_ROOM,
        namespace="/chat",
    )


async def emit_global_chat_cleared() -> None:
    await sio.emit(
        "chat_cleared",
        {},
        room=GLOBAL_CHAT_ROOM,
        namespace="/chat",
    )
    await sio.emit(
        "chat_unread_targets",
        {"message_ids": []},
        room=GLOBAL_CHAT_ROOM,
        namespace="/chat",
    )
    await sio.emit(
        "chat_unread_count",
        {"count": 0},
        namespace="/auth",
    )


def normalize_global_chat_image_object_key(raw: object) -> str | None:
    key = str(raw or "").strip()
    if not key:
        return None

    if not GLOBAL_CHAT_IMAGE_KEY_RE.match(key):
        raise ValueError("bad_image_key")

    if not key.startswith(f"{CHAT_IMAGE_PREFIX}/"):
        raise ValueError("forbidden_image_prefix")

    if ".." in key or "//" in key or key.endswith("/"):
        raise ValueError("bad_image_key")

    return key


def is_global_chat_image_owned_by_user(user_id: int, key: str | None) -> bool:
    uid = _positive_int(user_id)
    key_value = str(key or "").strip()
    if uid <= 0 or not key_value:
        return False

    return (
        key_value.startswith(f"{CHAT_IMAGE_PREFIX}/{uid}/")
        or key_value.startswith(f"{CHAT_IMAGE_PREFIX}/{CHAT_IMAGE_PENDING_SEGMENT}/{uid}/")
    )


def ensure_global_chat_image_owned_by_user(user_id: int, key: str | None) -> None:
    if not key:
        return

    if not is_global_chat_image_owned_by_user(user_id, key):
        raise ValueError("forbidden_image_owner")


async def serialize_global_chat_messages(session: AsyncSession, messages: Sequence[GlobalChatMessage], *, viewer_user_id: int | None, viewer_permissions: GlobalChatPermissions | None = None) -> list[dict[str, Any]]:
    if not messages:
        return []

    viewer_id = _positive_int(viewer_user_id)
    message_ids = [int(message.id) for message in messages]
    reply_ids = sorted({_positive_int(message.reply_to_message_id) for message in messages if _positive_int(message.reply_to_message_id) > 0})

    reply_map: dict[int, GlobalChatMessage] = {}
    if reply_ids:
        rows = await session.execute(select(GlobalChatMessage).where(GlobalChatMessage.id.in_(reply_ids)))
        reply_map = {int(message.id): message for message in rows.scalars().all()}

    user_ids: set[int] = {int(message.user_id) for message in messages}
    user_ids.update(int(message.user_id) for message in reply_map.values())
    if viewer_id > 0:
        user_ids.add(viewer_id)

    mention_spans_by_message_id, mention_user_ids, mentioned_usernames = _collect_message_mention_context(messages)
    reply_mention_spans_by_message_id, reply_mention_user_ids, reply_mentioned_usernames = _collect_message_mention_context(reply_map.values())
    user_ids.update(mention_user_ids)
    user_ids.update(reply_mention_user_ids)
    profiles = await get_user_profiles_cached(session, user_ids) if user_ids else {}
    resolved_mentions = await _resolve_mentioned_users(session, mentioned_usernames | reply_mentioned_usernames)
    viewer_profile = profiles.get(viewer_id) or {}
    viewer_role = normalize_user_role(viewer_profile.get("role"))
    viewer_is_chat_moderator = is_chat_moderator_role(viewer_role)
    viewer_can_delete_own = False
    if viewer_id > 0:
        if viewer_is_chat_moderator:
            viewer_can_delete_own = True
        else:
            permissions = viewer_permissions
            if permissions is None:
                permissions = await resolve_global_chat_permissions(session, viewer_id)
            viewer_can_delete_own = bool(permissions.can_delete_own)

    reaction_rows = await session.execute(
        select(
            GlobalChatMessageReaction.message_id,
            GlobalChatMessageReaction.user_id,
            GlobalChatMessageReaction.emoji,
        ).where(GlobalChatMessageReaction.message_id.in_(message_ids))
    )
    reaction_counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    reaction_by_me: dict[int, set[str]] = defaultdict(set)
    for message_id_raw, user_id_raw, emoji_raw in reaction_rows.all():
        message_id = _positive_int(message_id_raw)
        if message_id <= 0:
            continue
        emoji = str(emoji_raw or "")
        if not emoji:
            continue
        reaction_counts[message_id][emoji] += 1
        if 0 < viewer_id == _positive_int(user_id_raw):
            reaction_by_me[message_id].add(emoji)

    serialized: list[dict[str, Any]] = []
    for message in messages:
        public = _message_public_dict(message)
        author_profile = profiles.get(public["user_id"]) or {}
        author_role = normalize_user_role(author_profile.get("role"))
        deleted = bool(public["deleted"])
        own_message = 0 < viewer_id == public["user_id"]
        can_moderate_message = can_moderate_chat_message(
            actor_role=viewer_role,
            target_role=author_role,
            actor_user_id=viewer_id,
            target_user_id=public["user_id"],
        )
        can_delete_message = False
        if not deleted:
            if own_message:
                can_delete_message = bool(viewer_can_delete_own)
            else:
                can_delete_message = bool(viewer_is_chat_moderator and can_moderate_message)

        can_preview_deleted_message = bool(
            deleted
            and public.get("deleted_content_available")
            and can_view_deleted_chat_message(actor_role=viewer_role)
        )
        can_purge_deleted_message_flag = bool(
            deleted
            and public.get("deleted_content_available")
            and can_purge_deleted_chat_message(actor_role=viewer_role)
        )

        reactions: list[dict[str, Any]] = []
        if not deleted:
            counts = reaction_counts.get(public["id"], {})
            mine = reaction_by_me.get(public["id"], set())
            for emoji in GLOBAL_CHAT_REACTIONS_ALLOWLIST:
                count = int(counts.get(emoji) or 0)
                if count <= 0:
                    continue
                reactions.append(
                    {
                        "emoji": emoji,
                        "count": count,
                        "reacted_by_me": emoji in mine,
                    }
                )

        reply_payload: dict[str, Any] | None = None
        reply_to_message_id = public["reply_to_message_id"]
        if reply_to_message_id:
            reply_message = reply_map.get(int(reply_to_message_id))
            if reply_message is not None:
                reply_deleted = reply_message.deleted_at is not None
                reply_profile = profiles.get(int(reply_message.user_id)) or {}
                reply_text = str(reply_message.text or "")
                reply_mention_spans = reply_mention_spans_by_message_id.get(int(reply_message.id)) or []
                if reply_mention_spans:
                    reply_text = _render_text_with_mention_spans(reply_text, reply_mention_spans, profiles)
                reply_payload = {
                    "message_id": int(reply_message.id),
                    "author_username": _username_for(reply_profile, int(reply_message.user_id)),
                    "avatar_name": reply_profile.get("avatar_name"),
                    "snippet": "Сообщение удалено"
                    if reply_deleted
                    else _reply_snippet(reply_text, has_image=bool(reply_message.image_object_key)),
                    "deleted": reply_deleted,
                    "has_image": bool(reply_message.image_object_key) if not reply_deleted else False,
                }

        rendered_text = public["text"]
        mentions_payload: list[dict[str, Any]] = []
        if not deleted:
            mention_spans = mention_spans_by_message_id.get(public["id"]) or []
            if mention_spans:
                rendered_text = _render_text_with_mention_spans(public["text"], mention_spans, profiles)
                mentions_payload = _build_mentions_payload_from_spans(mention_spans, profiles)
            else:
                mentions_payload = _build_mentions_payload(public["text"], resolved_mentions)

        serialized.append(
            {
                "id": public["id"],
                "created_at": public["created_at"].isoformat(),
                "deleted": deleted,
                "deleted_at": public["deleted_at"].isoformat() if public["deleted_at"] else None,
                "deleted_content_available": bool(public.get("deleted_content_available")),
                "text": rendered_text,
                "author": {
                    "id": public["user_id"],
                    "username": _username_for(author_profile, public["user_id"]),
                    "avatar_name": author_profile.get("avatar_name"),
                    "theme_color": author_profile.get("theme_color"),
                    "theme_icon": author_profile.get("theme_icon"),
                    "role": author_role,
                    "deleted": _profile_deleted(author_profile),
                },
                "is_own": own_message,
                "can_delete": can_delete_message,
                "can_preview_deleted": can_preview_deleted_message,
                "can_purge_deleted": can_purge_deleted_message_flag,
                "reactions": reactions,
                "reply": reply_payload,
                "image_object_key": public["image_object_key"],
                "mentions": [] if deleted else mentions_payload,
            }
        )

    return serialized


async def fetch_global_chat_reaction_participants(session: AsyncSession, *, message_id: int) -> list[dict[str, Any]]:
    mid = _positive_int(message_id)
    if mid <= 0:
        return []

    rows = await session.execute(
        select(
            GlobalChatMessageReaction.user_id,
            GlobalChatMessageReaction.emoji,
            GlobalChatMessageReaction.created_at,
        )
        .where(GlobalChatMessageReaction.message_id == mid)
        .order_by(
            GlobalChatMessageReaction.created_at.asc(),
            GlobalChatMessageReaction.user_id.asc(),
            GlobalChatMessageReaction.emoji.asc(),
        )
    )

    items = rows.all()
    if not items:
        return []

    user_ids = {_positive_int(user_id) for user_id, _, _ in items if _positive_int(user_id) > 0}
    profiles = await get_user_profiles_cached(session, user_ids) if user_ids else {}

    participants: list[dict[str, Any]] = []
    for user_id_raw, emoji_raw, created_at_raw in items:
        user_id = _positive_int(user_id_raw)
        emoji = str(emoji_raw or "")
        if user_id <= 0 or not emoji:
            continue
        profile = profiles.get(user_id) or {}
        created_at = created_at_raw.isoformat() if isinstance(created_at_raw, datetime) else None
        participants.append(
            {
                "emoji": emoji,
                "created_at": created_at,
                "user": {
                    "id": user_id,
                    "username": _username_for(profile, user_id),
                    "avatar_name": profile.get("avatar_name"),
                    "theme_color": profile.get("theme_color"),
                    "theme_icon": profile.get("theme_icon"),
                    "role": profile.get("role"),
                    "deleted": _profile_deleted(profile),
                },
            }
        )

    return participants


async def emit_global_chat_profile_theme_sync(user_id: int, theme_color: str | None, theme_icon: str | None) -> None:
    uid = _positive_int(user_id)
    if uid <= 0:
        return

    normalized_color = theme_color.strip() if isinstance(theme_color, str) and theme_color.strip() else None
    normalized_icon = theme_icon.strip() if isinstance(theme_icon, str) and theme_icon.strip() else None
    await sio.emit(
        "chat_profile_theme_sync",
        {
            "user_id": uid,
            "theme_color": normalized_color,
            "theme_icon": normalized_icon,
        },
        room=GLOBAL_CHAT_ROOM,
        namespace="/chat",
    )


async def emit_global_chat_role_sync(user_id: int, role: str | None = None) -> None:
    uid = _positive_int(user_id)
    if uid <= 0:
        return

    normalized_role = normalize_user_role(role)

    try:
        participants = tuple(sio.manager.get_participants("/chat", f"user:{uid}"))
    except Exception:
        participants = ()

    for sid, _ in participants:
        try:
            sess = await sio.get_session(sid, namespace="/chat")
        except Exception:
            continue
        if not sess:
            continue

        next_session = dict(sess)
        next_session["role"] = normalized_role
        try:
            await sio.save_session(sid, next_session, namespace="/chat")
        except Exception:
            pass

    await sio.emit(
        "chat_role_sync",
        {
            "user_id": uid,
            "role": normalized_role,
        },
        room=GLOBAL_CHAT_ROOM,
        namespace="/chat",
    )
    await sio.emit(
        "chat_refresh_requested",
        {},
        room=global_chat_open_user_room(uid),
        namespace="/chat",
    )


async def get_global_chat_message(session: AsyncSession, message_id: int) -> GlobalChatMessage | None:
    mid = _positive_int(message_id)
    if mid <= 0:
        return None

    return await session.get(GlobalChatMessage, mid)


async def get_global_chat_message_by_client_id(session: AsyncSession, *, user_id: int, client_message_id: UUID) -> GlobalChatMessage | None:
    row = await session.execute(
        select(GlobalChatMessage).where(
            GlobalChatMessage.user_id == int(user_id),
            GlobalChatMessage.client_message_id == client_message_id,
        ).limit(1)
    )
    return row.scalar_one_or_none()


async def fetch_global_chat_page(session: AsyncSession, *, viewer_user_id: int, before_id: int | None = None, limit: int | None = None, viewer_permissions: GlobalChatPermissions | None = None) -> tuple[list[dict[str, Any]], bool, int | None]:
    page_limit = _normalize_limit(limit)
    before = _positive_int(before_id)
    if before_id is not None and before <= 0:
        return [], False, None

    stmt = select(GlobalChatMessage).order_by(GlobalChatMessage.id.desc()).limit(page_limit + 1)
    if before > 0:
        stmt = stmt.where(GlobalChatMessage.id < before)

    rows = await session.execute(stmt)
    items = rows.scalars().all()
    has_more = len(items) > page_limit
    items = items[:page_limit]
    items = list(reversed(items))
    messages = await serialize_global_chat_messages(
        session,
        items,
        viewer_user_id=viewer_user_id,
        viewer_permissions=viewer_permissions,
    )
    cursor_before_id = int(messages[0]["id"]) if messages else None
    return messages, has_more, cursor_before_id


async def fetch_global_chat_context(session: AsyncSession, *, viewer_user_id: int, message_id: int, window: int = GLOBAL_CHAT_CONTEXT_WINDOW, viewer_permissions: GlobalChatPermissions | None = None) -> list[dict[str, Any]]:
    target = await get_global_chat_message(session, message_id)
    if target is None:
        return []

    ctx_window = _normalize_limit(window, default=GLOBAL_CHAT_CONTEXT_WINDOW, max_value=GLOBAL_CHAT_CONTEXT_WINDOW)
    before_rows = await session.execute(
        select(GlobalChatMessage)
        .where(GlobalChatMessage.id < int(target.id))
        .order_by(GlobalChatMessage.id.desc())
        .limit(ctx_window)
    )
    after_rows = await session.execute(
        select(GlobalChatMessage)
        .where(GlobalChatMessage.id > int(target.id))
        .order_by(GlobalChatMessage.id.asc())
        .limit(ctx_window)
    )

    combined = list(reversed(before_rows.scalars().all())) + [target] + after_rows.scalars().all()
    deduped: list[GlobalChatMessage] = []
    seen: set[int] = set()
    for message in combined:
        message_id_int = int(message.id)
        if message_id_int in seen:
            continue
        seen.add(message_id_int)
        deduped.append(message)

    return await serialize_global_chat_messages(
        session,
        deduped,
        viewer_user_id=viewer_user_id,
        viewer_permissions=viewer_permissions,
    )


async def create_global_chat_message(session: AsyncSession, *, user_id: int, client_message_id: UUID, text: str, reply_to_message_id: int | None, image_object_key: str | None, silent_mention_user_ids: Sequence[int] | None = None) -> tuple[GlobalChatMessage, bool]:
    resolved_mentions = await _resolve_mentioned_users(session, set(_extract_mentioned_usernames(text)))
    mention_spans = _build_mention_spans(text, resolved_mentions, silent_user_ids=silent_mention_user_ids)
    stmt = (
        insert(GlobalChatMessage)
        .values(
            user_id=int(user_id),
            client_message_id=client_message_id,
            text=str(text),
            reply_to_message_id=_positive_int(reply_to_message_id) or None,
            image_object_key=image_object_key,
            mention_spans=mention_spans,
        )
        .on_conflict_do_nothing(index_elements=["user_id", "client_message_id"])
        .returning(GlobalChatMessage.id)
    )
    inserted_id = await session.scalar(stmt)
    if inserted_id is not None:
        await session.commit()
        created = await get_global_chat_message(session, int(inserted_id))
        if created is not None:
            return created, True

    existing = await get_global_chat_message_by_client_id(session, user_id=int(user_id), client_message_id=client_message_id)
    if existing is None:
        raise RuntimeError("global_chat_insert_failed")

    return existing, False


async def publish_global_chat_notice(session: AsyncSession, *, author_user_id: int, text: str, silent_mention_user_ids: Sequence[int] | None = None) -> dict[str, Any] | None:
    uid = _positive_int(author_user_id)
    normalized_text = _sanitize_text(text).strip()
    if uid <= 0 or not normalized_text:
        return None

    message, created = await create_global_chat_message(
        session,
        user_id=uid,
        client_message_id=uuid4(),
        text=normalized_text,
        reply_to_message_id=None,
        image_object_key=None,
        silent_mention_user_ids=silent_mention_user_ids,
    )
    if not created:
        return None

    alert_user_ids: set[int] = set()
    try:
        alert_user_ids = await get_global_chat_alert_user_ids(session, message_id=int(message.id))
        if alert_user_ids:
            await mark_global_chat_alert_read_for_open_users(
                session,
                message_id=int(message.id),
                user_ids=tuple(alert_user_ids),
            )
    except Exception:
        log.exception("global_chat.notice_alert_prepare_failed", message_id=int(message.id))

    payload = await build_global_chat_message_payload(session, message_id=int(message.id), viewer_user_id=None)
    if payload is not None:
        await sio.emit("chat_message_created", payload, room=GLOBAL_CHAT_ROOM, namespace="/chat")
    if alert_user_ids:
        try:
            await emit_global_chat_unread_states(tuple(alert_user_ids))
        except Exception:
            log.exception(
                "global_chat.notice_unread_emit_failed",
                message_id=int(message.id),
                user_ids=sorted(alert_user_ids),
            )

    return payload


async def emit_global_chat_sanction_issued_notice(session: AsyncSession, *, actor_user_id: int | None, target_user_id: int, target_username: str | None, kind: str, reason: str, duration_label: str | None = None) -> dict[str, Any] | None:
    author_user_id = await _resolve_global_chat_notice_author_user_id(session, preferred_user_id=actor_user_id)
    if author_user_id is None:
        return None

    resolved_target_username = await _resolve_chat_notice_target_username(
        session,
        user_id=target_user_id,
        username=target_username,
    )
    text = build_global_chat_sanction_issued_text(
        target_username=resolved_target_username,
        kind=kind,
        reason=reason,
        duration_label=duration_label,
    )
    return await publish_global_chat_notice(session, author_user_id=author_user_id, text=text)


async def emit_global_chat_sanction_removed_notice(session: AsyncSession, *, actor_user_id: int | None, target_user_id: int, target_username: str | None, kind: str, reason: str, source: str, remaining_duration_label: str | None = None) -> dict[str, Any] | None:
    author_user_id = await _resolve_global_chat_notice_author_user_id(session, preferred_user_id=actor_user_id)
    if author_user_id is None:
        return None

    resolved_target_username = await _resolve_chat_notice_target_username(
        session,
        user_id=target_user_id,
        username=target_username,
    )
    text = build_global_chat_sanction_removed_text(
        target_username=resolved_target_username,
        kind=kind,
        reason=reason,
        source=source,
        remaining_duration_label=remaining_duration_label,
    )

    return await publish_global_chat_notice(session, author_user_id=author_user_id, text=text)


async def emit_global_chat_sanction_adjusted_notice(session: AsyncSession, *, actor_user_id: int | None, target_user_id: int, target_username: str | None, kind: str, action: str, duration_label: str, remaining_duration_label: str | None = None) -> dict[str, Any] | None:
    author_user_id = await _resolve_global_chat_notice_author_user_id(session, preferred_user_id=actor_user_id)
    if author_user_id is None:
        return None

    resolved_target_username = await _resolve_chat_notice_target_username(
        session,
        user_id=target_user_id,
        username=target_username,
    )
    text = build_global_chat_sanction_adjusted_text(
        target_username=resolved_target_username,
        kind=kind,
        action=action,
        duration_label=duration_label,
        remaining_duration_label=remaining_duration_label,
    )
    return await publish_global_chat_notice(session, author_user_id=author_user_id, text=text)


async def emit_global_chat_nickname_reset_notice(
    session: AsyncSession,
    *,
    actor_user_id: int | None,
    target_user_id: int,
    previous_username: str | None,
    new_username: str | None,
) -> dict[str, Any] | None:
    author_user_id = await _resolve_global_chat_notice_author_user_id(
        session,
        preferred_user_id=actor_user_id,
    )
    if author_user_id is None:
        return None

    resolved_new_username = await _resolve_chat_notice_target_username(
        session,
        user_id=target_user_id,
        username=new_username,
    )
    previous = str(previous_username or "").strip() or resolved_new_username
    text = build_global_chat_nickname_reset_text(
        previous_username=previous,
        new_username=resolved_new_username,
    )
    return await publish_global_chat_notice(session, author_user_id=author_user_id, text=text)


async def emit_global_chat_avatar_deleted_notice(
    session: AsyncSession,
    *,
    actor_user_id: int | None,
    target_user_id: int,
    target_username: str | None,
) -> dict[str, Any] | None:
    author_user_id = await _resolve_global_chat_notice_author_user_id(
        session,
        preferred_user_id=actor_user_id,
    )
    if author_user_id is None:
        return None

    resolved_target_username = await _resolve_chat_notice_target_username(
        session,
        user_id=target_user_id,
        username=target_username,
    )
    text = build_global_chat_avatar_deleted_text(target_username=resolved_target_username)
    return await publish_global_chat_notice(session, author_user_id=author_user_id, text=text)


async def emit_global_chat_role_notice(session: AsyncSession, *, actor_user_id: int | None, target_user_id: int, target_username: str | None, role: str, granted: bool, silent_target_mention: bool = False) -> dict[str, Any] | None:
    author_user_id = await _resolve_global_chat_notice_author_user_id(session, preferred_user_id=actor_user_id)
    if author_user_id is None:
        return None

    resolved_target_username = await _resolve_chat_notice_target_username(
        session,
        user_id=target_user_id,
        username=target_username,
    )
    text = build_global_chat_role_changed_text(
        target_username=resolved_target_username,
        role=role,
        granted=granted,
    )

    silent_mention_user_ids: Sequence[int] | None = None
    if silent_target_mention and _positive_int(target_user_id) > 0:
        silent_mention_user_ids = (int(target_user_id),)

    return await publish_global_chat_notice(
        session,
        author_user_id=author_user_id,
        text=text,
        silent_mention_user_ids=silent_mention_user_ids,
    )


async def get_global_chat_reaction_alert_user_ids(session: AsyncSession, *, message_id: int) -> set[int]:
    message_id_int = _positive_int(message_id)
    if message_id_int <= 0:
        return set()

    rows = await session.execute(
        select(GlobalChatReactionAlert.user_id)
        .where(GlobalChatReactionAlert.message_id == message_id_int)
    )
    return {
        uid
        for uid in (_positive_int(row[0]) for row in rows.all())
        if uid > 0
    }


async def _upsert_global_chat_reaction_alert(session: AsyncSession, *, message: GlobalChatMessage, actor_user_id: int, now: datetime) -> tuple[int, ...]:
    owner_user_id = _positive_int(message.user_id)
    actor_id = _positive_int(actor_user_id)
    message_id = _positive_int(message.id)
    if owner_user_id <= 0 or actor_id <= 0 or message_id <= 0:
        return ()

    if owner_user_id == actor_id or message.deleted_at is not None:
        return ()

    if await is_user_blacklisted_by(session, owner_id=owner_user_id, target_id=actor_id):
        return ()

    alert = await session.get(
        GlobalChatReactionAlert,
        {
            "user_id": owner_user_id,
            "message_id": message_id,
        },
    )
    if alert is None:
        session.add(
            GlobalChatReactionAlert(
                user_id=owner_user_id,
                message_id=message_id,
                created_at=now,
                updated_at=now,
            )
        )
    else:
        alert.updated_at = now

    return (owner_user_id,)


async def _clear_global_chat_reaction_alert_if_no_pending_reactions(session: AsyncSession, *, message: GlobalChatMessage) -> tuple[int, ...]:
    owner_user_id = _positive_int(message.user_id)
    message_id = _positive_int(message.id)
    if owner_user_id <= 0 or message_id <= 0:
        return ()

    alert = await session.get(
        GlobalChatReactionAlert,
        {
            "user_id": owner_user_id,
            "message_id": message_id,
        },
    )
    if alert is None:
        return ()

    threshold = alert.created_at or alert.updated_at
    stmt = (
        select(func.count())
        .select_from(GlobalChatMessageReaction)
        .where(
            GlobalChatMessageReaction.message_id == message_id,
            GlobalChatMessageReaction.user_id != owner_user_id,
        )
    )
    if isinstance(threshold, datetime):
        stmt = stmt.where(GlobalChatMessageReaction.created_at >= threshold)

    remaining_reactions = int(await session.scalar(stmt) or 0)
    if remaining_reactions > 0:
        return ()

    await session.delete(alert)
    return (owner_user_id,)


async def clear_global_chat_reaction_alerts(session: AsyncSession, *, message_id: int) -> set[int]:
    message_id_int = _positive_int(message_id)
    if message_id_int <= 0:
        return set()

    user_ids = await get_global_chat_reaction_alert_user_ids(session, message_id=message_id_int)
    if user_ids:
        await session.execute(
            delete(GlobalChatReactionAlert)
            .where(GlobalChatReactionAlert.message_id == message_id_int)
        )

    return user_ids


async def toggle_global_chat_reaction(session: AsyncSession, *, message_id: int, user_id: int, emoji: str) -> tuple[bool, tuple[int, ...]]:
    message_id_int = _positive_int(message_id)
    user_id_int = _positive_int(user_id)
    if message_id_int <= 0 or user_id_int <= 0:
        raise ValueError("bad_message_id")

    emoji_value = str(emoji or "")
    if emoji_value not in GLOBAL_CHAT_REACTIONS_ALLOWLIST:
        raise ValueError("emoji_not_allowed")

    message = await session.scalar(
        select(GlobalChatMessage)
        .where(GlobalChatMessage.id == message_id_int)
        .with_for_update()
    )
    if message is None:
        raise ValueError("message_not_found")

    existing = await session.get(
        GlobalChatMessageReaction,
        {
            "message_id": message_id_int,
            "user_id": user_id_int,
            "emoji": emoji_value,
        },
    )
    if existing is not None:
        await session.delete(existing)
        await session.flush()
        alert_user_ids = await _clear_global_chat_reaction_alert_if_no_pending_reactions(
            session,
            message=message,
        )
        await session.commit()
        return False, alert_user_ids

    now = datetime.now(timezone.utc)
    session.add(
        GlobalChatMessageReaction(
            message_id=message_id_int,
            user_id=user_id_int,
            emoji=emoji_value,
            created_at=now,
        )
    )
    alert_user_ids = await _upsert_global_chat_reaction_alert(
        session,
        message=message,
        actor_user_id=user_id_int,
        now=now,
    )
    await session.commit()
    return True, alert_user_ids


async def delete_global_chat_message(session: AsyncSession, *, message: GlobalChatMessage, actor_user_id: int) -> GlobalChatMessage:
    if message.deleted_at is None:
        message.deleted_at = datetime.now(timezone.utc)
        message.deleted_by_user_id = int(actor_user_id)
        await session.commit()
    return message


async def build_deleted_global_chat_message_preview(session: AsyncSession, *, message: GlobalChatMessage) -> dict[str, Any]:
    author_id = int(message.user_id)
    author_profile = {}
    if author_id > 0:
        profiles = await get_user_profiles_cached(session, {author_id})
        author_profile = profiles.get(author_id) or {}

    content_available = bool(str(message.text or "").strip()) or bool(message.image_object_key)
    raw_text = str(message.text or "")
    mention_spans = _normalize_mention_spans(getattr(message, "mention_spans", None), text_len=len(raw_text))
    mention_user_ids = _mentioned_user_ids_from_spans(mention_spans)
    mention_profiles = await get_user_profiles_cached(session, mention_user_ids) if mention_user_ids else {}
    resolved_mentions = (
        {}
        if mention_spans
        else await _resolve_mentioned_users(session, set(_extract_mentioned_usernames(raw_text)))
    )
    preview_text = _render_text_with_mention_spans(raw_text, mention_spans, mention_profiles) if mention_spans else raw_text
    return {
        "message_id": int(message.id),
        "deleted_at": message.deleted_at.isoformat() if message.deleted_at else None,
        "content_available": content_available,
        "text": preview_text if content_available else "",
        "image_object_key": str(message.image_object_key) if content_available and message.image_object_key else None,
        "mentions": (
            _build_mentions_payload_from_spans(mention_spans, mention_profiles)
            if content_available and mention_spans
            else (_build_mentions_payload(raw_text, resolved_mentions) if content_available else [])
        ),
        "author": {
            "id": author_id,
            "username": _username_for(author_profile, author_id),
            "avatar_name": author_profile.get("avatar_name"),
            "theme_color": author_profile.get("theme_color"),
            "theme_icon": author_profile.get("theme_icon"),
            "role": author_profile.get("role"),
            "deleted": _profile_deleted(author_profile),
        },
    }


async def purge_global_chat_message(session: AsyncSession, *, message: GlobalChatMessage) -> tuple[GlobalChatMessage, bool]:
    image_key = str(message.image_object_key or "").strip() or None
    had_content = bool(str(message.text or "").strip()) or bool(image_key)
    if not had_content:
        return message, False

    message.text = ""
    message.image_object_key = None
    message.mention_spans = []
    await session.commit()

    if image_key:
        try:
            if not await is_global_chat_image_referenced(session, image_key):
                await delete_object_async(image_key)
        except Exception:
            log.exception("global_chat.purge_image_cleanup_failed", message_id=int(message.id), key=image_key)

    return message, True


async def build_global_chat_message_payload(session: AsyncSession, *, message_id: int, viewer_user_id: int | None, viewer_permissions: GlobalChatPermissions | None = None) -> dict[str, Any] | None:
    message = await get_global_chat_message(session, message_id)
    if message is None:
        return None
    payloads = await serialize_global_chat_messages(
        session,
        [message],
        viewer_user_id=viewer_user_id,
        viewer_permissions=viewer_permissions,
    )
    return payloads[0] if payloads else None


async def is_global_chat_image_referenced(session: AsyncSession, key: str | None) -> bool:
    key_value = str(key or "").strip()
    if not key_value:
        return False

    row = await session.execute(
        select(GlobalChatMessage.id)
        .where(GlobalChatMessage.image_object_key == key_value)
        .limit(1)
    )
    return row.scalar_one_or_none() is not None


async def validate_global_chat_send_input(*, user_id: int, text: object, reply_to_message_id: object, image_object_key: object) -> tuple[str, int | None, str | None]:
    normalized_text = _sanitize_text(text)
    reply_id = _positive_int(reply_to_message_id) or None
    image_key = normalize_global_chat_image_object_key(image_object_key)
    if not normalized_text.strip() and not image_key:
        raise ValueError("empty_message")

    if image_key:
        ensure_global_chat_image_owned_by_user(user_id, image_key)

    return normalized_text, reply_id, image_key


async def finalize_global_chat_image(*, user_id: int, image_object_key: str | None) -> str | None:
    image_key = normalize_global_chat_image_object_key(image_object_key)
    if not image_key:
        return None

    ensure_global_chat_image_owned_by_user(user_id, image_key)
    return await validate_chat_image_object_async(image_key)


async def delete_global_chat_image_if_unreferenced(image_object_key: str | None) -> None:
    key = normalize_global_chat_image_object_key(image_object_key)
    if not key:
        return

    async with SessionLocal() as session:
        if await is_global_chat_image_referenced(session, key):
            return

    await delete_object_async(key)
