from __future__ import annotations
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import UUID, uuid4
import structlog
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.global_chat import GlobalChatMessage, GlobalChatMessageReaction
from ..models.sanction import UserSanction
from ..models.user import User
from ..core.db import SessionLocal
from ..realtime.sio import sio
from ..security.parameters import get_cached_settings
from ..api.utils import is_user_in_active_alive_game
from ..services.minio import CHAT_IMAGE_PREFIX, delete_object_async, object_exists_async, validate_chat_image_object_async
from ..services.user_cache import get_user_profiles_cached

log = structlog.get_logger()

GLOBAL_CHAT_ROOM = "global_chat:open"
GLOBAL_CHAT_OPEN_USER_ROOM_PREFIX = "global_chat:user_open"
GLOBAL_CHAT_HISTORY_LIMIT = 100
GLOBAL_CHAT_CONTEXT_WINDOW = 25
GLOBAL_CHAT_MAX_TEXT_LEN = 1000
GLOBAL_CHAT_IMAGE_KEY_RE = re.compile(r"^[a-zA-Z0-9._/-]{3,256}$")
SANCTION_RULE_POINT_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)*)\.")
GLOBAL_CHAT_REACTIONS_ALLOWLIST: tuple[str, ...] = (
    "👍",
    "👎",
    "❤️",
    "🔥",
    "😂",
    "😭",
    "😡",
    "🤮",
    "🤡",
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
    in_active_game_as_alive_player: bool
    telegram_verified: bool
    error: str | None = None


def _positive_int(raw: object) -> int:
    try:
        value = int(raw)
    except Exception:
        return 0

    return value if value > 0 else 0


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


def build_global_chat_sanction_issued_text(*, target_username: str, kind: str, reason: str, duration_label: str | None = None) -> str:
    kind_value = str(kind or "").strip().lower()
    details = _format_sanction_reason_details(reason)
    duration = str(duration_label or "").strip()
    if kind_value == SANCTION_SUSPEND:
        base = f"Пользователь {target_username} отстранен от игр"
        if duration:
            base += f" на {duration}"
        return f"{base}{details}"

    if kind_value == SANCTION_TIMEOUT:
        base = f"Пользователь {target_username} получил таймаут"
        if duration:
            base += f" на {duration}"
        return f"{base}{details}"

    if kind_value == SANCTION_BAN:
        return f"Пользователь {target_username} был забанен{details}"

    base = f"Пользователь {target_username} получил {_sanction_kind_label(kind)}"
    if duration:
        base += f" на {duration}"
    return f"{base}{details}"


def build_global_chat_sanction_removed_text(*, target_username: str, kind: str, reason: str, source: str, remaining_duration_label: str | None = None) -> str:
    source_value = str(source or "").strip().lower()
    kind_value = str(kind or "").strip().lower()
    if source_value == "expired":
        if kind_value == SANCTION_TIMEOUT:
            return f"У пользователя {target_username} истек срок таймаута"

        if kind_value == SANCTION_SUSPEND:
            return f"У пользователя {target_username} истек срок отстранения от игр"

        return f"У пользователя {target_username} истек срок {_sanction_kind_label(kind)}"

    if source_value == "game":
        if kind_value == SANCTION_SUSPEND:
            return f"У пользователя {target_username} истек срок отстранения от игр (после проведенной игры)"

        return f"У пользователя {target_username} истек срок {_sanction_kind_label(kind)} (после проведенной игры)"

    remaining = str(remaining_duration_label or "").strip()
    remaining_suffix = f" (раньше срока на {remaining})" if remaining else ""
    if kind_value == SANCTION_TIMEOUT:
        return f"У пользователя {target_username} досрочно снят таймаут{remaining_suffix}"

    if kind_value == SANCTION_SUSPEND:
        return f"У пользователя {target_username} досрочно снято отстранение от игр{remaining_suffix}"

    if kind_value == SANCTION_BAN:
        return f"Пользователь {target_username} разбанен"

    return f"У пользователя {target_username} снята {_sanction_kind_label(kind)}"


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
            in_active_game_as_alive_player=False,
            telegram_verified=False,
            error="unauthorized",
        )

    sanctions = await _fetch_active_sanctions(session, int(user.id))
    timeout_active = sanctions.get(SANCTION_TIMEOUT) is not None
    ban_active = sanctions.get(SANCTION_BAN) is not None
    telegram_verified = bool(user.telegram_id)
    try:
        in_active_game_as_alive_player = await is_user_in_active_alive_game(int(user.id), strict=True)
    except RuntimeError:
        return GlobalChatPermissions(
            can_open=False,
            can_send=False,
            can_react=False,
            can_delete_own=False,
            timeout_active=timeout_active,
            ban_active=ban_active,
            in_active_game_as_alive_player=False,
            telegram_verified=telegram_verified,
            error="presence_unavailable",
        )

    can_open = True
    error: str | None = None
    if not get_cached_settings().chat_open_enabled:
        can_open = False
        error = "chat_disabled"
    elif ban_active:
        can_open = False
        error = "user_banned"
    elif timeout_active:
        can_open = False
        error = "user_timeout"
    elif in_active_game_as_alive_player:
        can_open = False
        error = "active_game_player"
    elif get_cached_settings().verification_restrictions and not telegram_verified:
        can_open = False
        error = "not_verified"

    can_send = can_open and bool(get_cached_settings().chat_messages_enabled)
    can_react = can_open
    can_delete_own = can_open

    return GlobalChatPermissions(
        can_open=can_open,
        can_send=can_send,
        can_react=can_react,
        can_delete_own=can_delete_own,
        timeout_active=timeout_active,
        ban_active=ban_active,
        in_active_game_as_alive_player=in_active_game_as_alive_player,
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


async def emit_global_chat_cleared() -> None:
    await sio.emit(
        "chat_cleared",
        {},
        room=GLOBAL_CHAT_ROOM,
        namespace="/chat",
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

    return key_value.startswith(f"{CHAT_IMAGE_PREFIX}/{uid}/")


def ensure_global_chat_image_owned_by_user(user_id: int, key: str | None) -> None:
    if not key:
        return

    if not is_global_chat_image_owned_by_user(user_id, key):
        raise ValueError("forbidden_image_owner")


async def ensure_global_chat_image_exists(key: str | None) -> None:
    if not key:
        return

    exists = await object_exists_async(key)
    if not exists:
        raise ValueError("image_not_found")


async def serialize_global_chat_messages(session: AsyncSession, messages: Sequence[GlobalChatMessage], *, viewer_user_id: int | None) -> list[dict[str, Any]]:
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
    profiles = await get_user_profiles_cached(session, user_ids) if user_ids else {}

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
        deleted = bool(public["deleted"])
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
                reply_payload = {
                    "message_id": int(reply_message.id),
                    "author_username": _username_for(reply_profile, int(reply_message.user_id)),
                    "snippet": "Сообщение удалено"
                    if reply_deleted
                    else _reply_snippet(str(reply_message.text or ""), has_image=bool(reply_message.image_object_key)),
                    "deleted": reply_deleted,
                    "has_image": bool(reply_message.image_object_key) if not reply_deleted else False,
                }

        serialized.append(
            {
                "id": public["id"],
                "created_at": public["created_at"].isoformat(),
                "deleted": deleted,
                "deleted_at": public["deleted_at"].isoformat() if public["deleted_at"] else None,
                "deleted_content_available": bool(public.get("deleted_content_available")),
                "text": public["text"],
                "author": {
                    "id": public["user_id"],
                    "username": _username_for(author_profile, public["user_id"]),
                    "avatar_name": author_profile.get("avatar_name"),
                },
                "is_own": 0 < viewer_id == public["user_id"],
                "can_delete": 0 < viewer_id == public["user_id"] and not deleted,
                "reactions": reactions,
                "reply": reply_payload,
                "image_object_key": public["image_object_key"],
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
                },
            }
        )

    return participants


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


async def fetch_global_chat_page(session: AsyncSession, *, viewer_user_id: int, before_id: int | None = None, limit: int | None = None) -> tuple[list[dict[str, Any]], bool, int | None]:
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
    messages = await serialize_global_chat_messages(session, items, viewer_user_id=viewer_user_id)
    cursor_before_id = int(messages[0]["id"]) if messages else None
    return messages, has_more, cursor_before_id


async def fetch_global_chat_context(session: AsyncSession, *, viewer_user_id: int, message_id: int, window: int = GLOBAL_CHAT_CONTEXT_WINDOW) -> list[dict[str, Any]]:
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

    return await serialize_global_chat_messages(session, deduped, viewer_user_id=viewer_user_id)


async def create_global_chat_message(session: AsyncSession, *, user_id: int, client_message_id: UUID, text: str, reply_to_message_id: int | None, image_object_key: str | None) -> tuple[GlobalChatMessage, bool]:
    stmt = (
        insert(GlobalChatMessage)
        .values(
            user_id=int(user_id),
            client_message_id=client_message_id,
            text=str(text),
            reply_to_message_id=_positive_int(reply_to_message_id) or None,
            image_object_key=image_object_key,
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


async def publish_global_chat_notice(session: AsyncSession, *, author_user_id: int, text: str) -> dict[str, Any] | None:
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
    )
    if not created:
        return None

    payload = await build_global_chat_message_payload(session, message_id=int(message.id), viewer_user_id=None)
    if payload is not None:
        await sio.emit("chat_message_created", payload, room=GLOBAL_CHAT_ROOM, namespace="/chat")

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


async def toggle_global_chat_reaction(session: AsyncSession, *, message_id: int, user_id: int, emoji: str) -> bool:
    message_id_int = _positive_int(message_id)
    user_id_int = _positive_int(user_id)
    if message_id_int <= 0 or user_id_int <= 0:
        raise ValueError("bad_message_id")

    emoji_value = str(emoji or "")
    if emoji_value not in GLOBAL_CHAT_REACTIONS_ALLOWLIST:
        raise ValueError("emoji_not_allowed")

    await session.execute(
        select(GlobalChatMessage.id)
        .where(GlobalChatMessage.id == message_id_int)
        .with_for_update()
    )

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
        await session.commit()
        return False

    session.add(
        GlobalChatMessageReaction(
            message_id=message_id_int,
            user_id=user_id_int,
            emoji=emoji_value,
        )
    )
    await session.commit()
    return True


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
    return {
        "message_id": int(message.id),
        "deleted_at": message.deleted_at.isoformat() if message.deleted_at else None,
        "content_available": content_available,
        "text": str(message.text or "") if content_available else "",
        "image_object_key": str(message.image_object_key) if content_available and message.image_object_key else None,
        "author": {
            "id": author_id,
            "username": _username_for(author_profile, author_id),
            "avatar_name": author_profile.get("avatar_name"),
        },
    }


async def purge_global_chat_message(session: AsyncSession, *, message: GlobalChatMessage) -> tuple[GlobalChatMessage, bool]:
    image_key = str(message.image_object_key or "").strip() or None
    had_content = bool(str(message.text or "").strip()) or bool(image_key)
    if not had_content:
        return message, False

    message.text = ""
    message.image_object_key = None
    await session.commit()

    if image_key:
        try:
            if not await is_global_chat_image_referenced(session, image_key):
                await delete_object_async(image_key)
        except Exception:
            log.exception("global_chat.purge_image_cleanup_failed", message_id=int(message.id), key=image_key)

    return message, True


async def build_global_chat_message_payload(session: AsyncSession, *, message_id: int, viewer_user_id: int | None) -> dict[str, Any] | None:
    message = await get_global_chat_message(session, message_id)
    if message is None:
        return None
    payloads = await serialize_global_chat_messages(session, [message], viewer_user_id=viewer_user_id)
    return payloads[0] if payloads else None


async def build_global_chat_reactions_payload(session: AsyncSession, *, message_id: int, viewer_user_id: int | None) -> dict[str, Any] | None:
    payload = await build_global_chat_message_payload(session, message_id=message_id, viewer_user_id=viewer_user_id)
    if payload is None:
        return None

    return {
        "message_id": int(payload["id"]),
        "reactions": payload["reactions"],
    }


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
        image_key = await validate_chat_image_object_async(image_key)

    return normalized_text, reply_id, image_key
