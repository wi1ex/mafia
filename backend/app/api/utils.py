from __future__ import annotations
import re
import secrets
import unicodedata
import asyncio
import calendar
from contextlib import suppress
import structlog
from time import time
from datetime import date, datetime, timezone, timedelta
from typing import Optional, Dict, Any, Literal, Sequence, Iterable, cast, TYPE_CHECKING
from fastapi import HTTPException, status, Header
from sqlalchemy import update, func, select, or_, and_, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.clients import get_redis
from ..core.db import SessionLocal
from ..core.logging import log_action
from ..core.roles import ROLE_USER, admin_users_role_sort_value, normalize_user_role, room_moderation_role
from ..core.settings import settings
from ..models.game import Game
from ..models.room import Room
from ..models.friend import FriendLink
from ..models.notif import Notif
from ..models.subscription import UserSubscription
from ..models.sanction import UserSanction
from ..models.user import User
from ..models.update import SiteUpdate, UpdateRead
from ..realtime.sio import sio
from ..security.admin_guard import is_protected_admin_uid
from ..services.minio import delete_avatars_async
from ..services.user_cache import (
    get_user_profiles_cached,
    refresh_user_profile_cache,
    write_user_profile_cache,
    invalidate_avatar_presign_cache,
)
from ..services.profile_theme import ensure_profile_theme_defaults, resolve_profile_theme_state
from ..services.telegram import send_text_message
if TYPE_CHECKING:
    from ..schemas.admin import SiteSettingsOut, GameSettingsOut, RegistrationsPoint, AdminRoomUserStat, AdminSanctionOut, AdminGameActionFieldOut
    from ..schemas.room import GameParams
    from ..schemas.user import UserGamesHistoryOut, GameHistoryItemOut, GameHistoryHostOut, UserStatsOut

__all__ = [
    "SANCTION_TIMEOUT",
    "SANCTION_BAN",
    "SANCTION_SUSPEND",
    "HOSTED_GAME_SUSPEND_REDUCTION_SECONDS",
    "USERS_SORT_DEFAULT",
    "TIMED_KINDS",
    "serialize_game_for_redis",
    "game_from_redis_to_model",
    "normalize_spectators_limit",
    "emit_rooms_upsert",
    "broadcast_creator_rooms",
    "emit_room_profile_theme_sync",
    "get_room_game_runtime",
    "build_room_members_for_info",
    "get_room_params_or_404",
    "touch_user_last_login",
    "active_alive_game_room_key",
    "active_game_rooms_key",
    "redis_text",
    "active_game_head_room_by_uid",
    "tg_room_invite_cooldown_key",
    "get_active_alive_game_room",
    "get_active_game_rooms",
    "is_user_in_active_alive_game",
    "is_user_in_active_game",
    "validate_object_key_for_presign",
    "parse_month_range",
    "parse_day_range",
    "site_settings_out",
    "game_settings_out",
    "schedule_room_gc",
    "gc_empty_room_and_emit",
    "normalize_pagination",
    "build_registrations_series",
    "build_registrations_monthly_series",
    "build_games_series",
    "build_games_monthly_series",
    "build_active_users_series",
    "build_active_users_monthly_series",
    "schedule_user_game_stats_cache_invalidation",
    "calc_total_stream_seconds",
    "calc_room_stream_seconds_in_range",
    "fetch_active_rooms_stats",
    "fetch_online_user_ids",
    "fetch_effective_online_user_ids",
    "fetch_user_avatar_map",
    "fetch_user_name_avatar_maps",
    "collect_room_user_ids",
    "parse_room_game_params",
    "build_room_user_stats",
    "sum_room_stream_seconds",
    "fetch_live_room_stats",
    "aggregate_user_room_time_stats",
    "aggregate_user_room_stats",
    "aggregate_user_games_in_owned_rooms_stats",
    "build_user_stats_out",
    "fetch_users_last_game_at",
    "fetch_users_last_room_id",
    "fetch_users_last_spectator_room_id",
    "normalize_users_sort",
    "normalize_moderation_users_sort",
    "fetch_friends_count_for_users",
    "fetch_sanction_counts_for_users",
    "admin_role_sort_key",
    "admin_username_sort_key",
    "user_sort_metric",
    "moderation_user_sort_metric",
    "compute_duration_seconds",
    "elapsed_seconds_since",
    "is_sanction_active",
    "fetch_active_sanction",
    "fetch_active_sanctions",
    "fetch_active_sanctions_for_users",
    "fetch_active_sanctions_by_telegram",
    "fetch_sanctions_for_users",
    "pick_active_sanction_kind",
    "build_admin_sanction_out",
    "sanction_status",
    "sanction_finished_at",
    "sanction_served_seconds",
    "sanction_actor_display",
    "revoke_active_suspend",
    "reduce_suspend_after_hosted_game",
    "emit_expired_timed_sanction_chat_notice_once",
    "emit_expired_timed_sanctions_chat_notices",
    "sync_expired_profile_subscriptions",
    "notify_expiring_profile_subscriptions",
    "notify_subscription_upsert",
    "maybe_send_sanction_telegram_if_offline",
    "delete_gif_avatar_for_inactive_subscription",
    "emit_sanctions_update",
    "build_user_out_payload",
    "emit_auth_profile_sync",
    "refresh_rooms_after",
    "ensure_room_access_allowed",
    "ensure_profile_changes_allowed",
    "is_protected_admin",
    "ensure_admin_target_allowed",
    "ensure_admin_target_not_deleted",
    "ensure_moderation_target_allowed",
    "get_moderation_target_user",
    "set_user_deleted",
    "delete_user_account_as_admin_action",
    "delete_stale_unverified_accounts",
    "delete_friend_links_for_user",
    "force_logout_user",
    "force_leave_user_from_rooms",
    "check_sanctions_expired",
    "format_duration_parts",
    "format_duration_seconds_compact",
    "format_subscription_until",
    "normalize_chat_mention_query",
    "normalize_username",
    "normalize_password",
    "normalize_username_search_term",
    "is_within_single_typo",
    "find_user_ids_by_username_search",
    "find_user_by_username",
    "generate_user_id",
    "init_updates_read",
    "require_bot_token",
    "pair",
    "load_link",
    "friend_status_for",
    "raise_missing_incoming_request_error",
    "raise_missing_outgoing_request_error",
    "emit_notify",
    "emit_friends_update",
    "emit_friends_profile_sync",
    "emit_role_change_friend_profile_syncs",
    "emit_room_role_sync",
    "sanitize_username_for_schema",
    "sanitize_title_for_schema",
    "parse_season_starts",
    "season_starts_csv",
    "parse_season_starts_or_default",
    "normalize_season_start_game_number",
    "parse_text_moderation_whitelist",
    "text_moderation_whitelist_csv",
    "normalize_text_moderation_whitelist",
    "parse_text_moderation_blacklist",
    "text_moderation_blacklist_csv",
    "normalize_text_moderation_blacklist",
    "normalize_admin_banner_text",
    "normalize_admin_banner_link",
    "normalize_season_start_value",
    "build_app_settings_snapshot_defaults",
    "build_app_settings_snapshot_from_row",
    "parse_cached_deleted_at",
    "safe_int",
    "non_empty_str",
    "normalize_game_result",
    "normalizeGameActionsForUpdate",
    "gameActionHasPpk",
    "findGamePpkTargetUserId",
    "findGameFoulDeathActionIndex",
    "findGameFoulActionIndex",
    "setGameActionPpk",
    "fetch_games_history_page",
    "game_action_slot_label",
    "game_action_slot_labels",
    "game_action_join",
    "game_action_role_label",
    "game_action_reason_label",
    "game_action_bool_label",
    "game_action_vote_pairs",
    "game_action_target_pairs",
    "game_action_wills",
    "game_action_check_result",
    "game_action_fields",
]

log = structlog.get_logger()


def normalize_spectators_limit(value: Any) -> int:
    if value is None:
        return 10

    try:
        parsed = int(value)
    except Exception:
        return 10

    return 0 if parsed <= 0 else 10


def schedule_user_game_stats_cache_invalidation(log_event: str, **log_kwargs: object) -> None:
    async def _task() -> None:
        try:
            from ..services.user_stats import invalidate_all_user_game_stats_cache

            await invalidate_all_user_game_stats_cache()
        except Exception:
            log.warning(log_event, **log_kwargs)

    asyncio.create_task(_task())

PRESIGN_ALLOWED_PREFIXES: tuple[str, ...] = ("avatars/", "chat/global/images/")
PRESIGN_KEY_RE = re.compile(r"^[a-zA-Z0-9._/-]{3,256}$")
BOT_USERNAME_RE = re.compile(r"^[a-zA-Zа-яА-ЯёЁ0-9._\-()]{2,20}$")
CHAT_MENTION_QUERY_RE = re.compile(r"^[a-zA-Zа-яА-ЯёЁ0-9._\-()]{1,20}$")
PWD_CTRL_RE = re.compile(r"[\x00-\x1F\x7F]")
PWD_WS_RE = re.compile(r"\s")
TITLE_CTRL_RE = re.compile(r"[\x00-\x1F\x7F]")
TITLE_BIDI_RE = re.compile(r"[\u200B-\u200F\u202A-\u202E\u2066-\u2069]")
TITLE_WS_RE = re.compile(r"\s+")

SANCTION_TIMEOUT = "timeout"
SANCTION_BAN = "ban"
SANCTION_SUSPEND = "suspend"
HOSTED_GAME_SUSPEND_REDUCTION_SECONDS = 4 * 60 * 60
EXPIRED_SANCTION_CHAT_NOTICE_TTL_S = 60 * 60 * 24 * 365
EXPIRED_SUBSCRIPTION_SYNC_TTL_S = 14 * 24 * 60 * 60
SUBSCRIPTION_EXPIRING_SOON_NOTICE_BEFORE = timedelta(days=3)
SUBSCRIPTION_EXPIRING_SOON_NOTICE_TTL_S = 14 * 24 * 60 * 60
AUTO_DELETE_UNVERIFIED_ACCOUNT_LOCK_TTL_S = 60 * 60
USERS_SORT_DEFAULT = "registered_at"
USERS_SORT_ALLOWED = {
    USERS_SORT_DEFAULT,
    "role",
    "username",
    "last_login_at",
    "last_visit_at",
    "last_game_at",
    "last_room_id",
    "last_spectator_room_id",
    "tg_invites_enabled",
    "friends_count",
    "rooms_created",
    "room_minutes",
    "stream_minutes",
    "games_played",
    "games_hosted",
    "spectator_minutes",
    "timeouts_count",
    "bans_count",
    "suspends_count",
}
MODERATION_USERS_SORT_ALLOWED = {
    USERS_SORT_DEFAULT,
    "username",
    "last_login_at",
    "last_visit_at",
    "last_game_at",
    "timeouts_count",
    "bans_count",
    "suspends_count",
}
TIMED_KINDS = {SANCTION_TIMEOUT, SANCTION_SUSPEND}
_RU_ALPHA = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
_EN_ALPHA = "abcdefghijklmnopqrstuvwxyz"
_RU_ALPHA_ORDER = {ch: idx for idx, ch in enumerate(_RU_ALPHA)}
_EN_ALPHA_ORDER = {ch: idx for idx, ch in enumerate(_EN_ALPHA)}


def sanitize_username_for_schema(v: Any) -> str:
    return unicodedata.normalize("NFKC", str(v or "")).strip()


def sanitize_title_for_schema(v: Any) -> str:
    s = unicodedata.normalize("NFKC", str(v or ""))
    s = TITLE_CTRL_RE.sub("", s)
    s = TITLE_BIDI_RE.sub("", s)
    s = TITLE_WS_RE.sub(" ", s).strip()
    return s


def elapsed_seconds_since(at: datetime | None) -> float | None:
    if at is None:
        return None

    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - at).total_seconds()


def _as_positive_int(raw: object) -> int:
    if raw is None:
        raise ValueError("season_start_invalid")

    try:
        value = int(str(raw).strip())
    except Exception as exc:
        raise ValueError("season_start_invalid") from exc

    if value < 1:
        raise ValueError("season_start_invalid")

    return value


def parse_season_starts(raw: object) -> tuple[int, ...]:
    if isinstance(raw, int):
        return (_as_positive_int(raw),)

    source = str(raw or "").strip()
    if not source:
        raise ValueError("season_start_empty")

    values: list[int] = []
    for part in source.split(","):
        token = part.strip()
        if not token:
            raise ValueError("season_start_invalid")

        values.append(_as_positive_int(token))

    if not values:
        raise ValueError("season_start_empty")

    return tuple(sorted(set(values)))


def season_starts_csv(values: Iterable[int]) -> str:
    out = [int(v) for v in values if int(v) > 0]
    if not out:
        return "1"

    return ",".join(str(v) for v in sorted(set(out)))


def parse_season_starts_or_default(raw: object, *, default: Sequence[int] = (1,)) -> tuple[int, ...]:
    try:
        return parse_season_starts(raw)

    except ValueError:
        fallback = [int(v) for v in default if int(v) > 0]
        if not fallback:
            fallback = [1]
        return tuple(sorted(set(fallback)))


def normalize_season_start_game_number(value: str) -> str:
    return season_starts_csv(parse_season_starts(value))


def _normalize_text_moderation_whitelist_word(raw: object) -> str:
    value = unicodedata.normalize("NFKC", str(raw or "")).strip().lower().replace("ё", "е")
    value = TITLE_WS_RE.sub(" ", value)
    return value


def parse_text_moderation_whitelist(raw: object) -> tuple[str, ...]:
    source = str(raw or "").strip()
    if not source or source == "0":
        return ()

    values: list[str] = []
    seen: set[str] = set()
    for part in source.split(","):
        word = _normalize_text_moderation_whitelist_word(part)
        if not word or word == "0" or word in seen:
            continue
        seen.add(word)
        values.append(word)

    return tuple(values)


def text_moderation_whitelist_csv(values: Iterable[str]) -> str:
    out: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        word = _normalize_text_moderation_whitelist_word(raw_value)
        if not word or word == "0" or word in seen:
            continue
        seen.add(word)
        out.append(word)

    if not out:
        return "0"

    return ",".join(out)


def normalize_text_moderation_whitelist(raw: object) -> str:
    return text_moderation_whitelist_csv(parse_text_moderation_whitelist(raw))


def _normalize_text_moderation_blacklist_word(raw: object) -> str:
    return _normalize_text_moderation_whitelist_word(raw)


def parse_text_moderation_blacklist(raw: object) -> tuple[str, ...]:
    source = str(raw or "").strip()
    if not source or source == "0":
        return ()

    values: list[str] = []
    seen: set[str] = set()
    for part in source.split(","):
        word = _normalize_text_moderation_blacklist_word(part)
        if not word or word == "0" or word in seen:
            continue
        seen.add(word)
        values.append(word)

    return tuple(values)


def text_moderation_blacklist_csv(values: Iterable[str]) -> str:
    out: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        word = _normalize_text_moderation_blacklist_word(raw_value)
        if not word or word == "0" or word in seen:
            continue
        seen.add(word)
        out.append(word)

    if not out:
        return "0"

    return ",".join(out)


def normalize_text_moderation_blacklist(raw: object) -> str:
    return text_moderation_blacklist_csv(parse_text_moderation_blacklist(raw))


def normalize_admin_banner_text(raw: object) -> str:
    value = str(raw or "").strip()
    if not value or value == "0":
        return "0"

    return value


def normalize_admin_banner_link(raw: object) -> str:
    value = str(raw or "").strip()
    if not value or value == "0":
        return "0"

    if value.startswith("/"):
        return value

    lowered = value.lower()
    if lowered.startswith("https://") or lowered.startswith("http://"):
        return value

    if "://" in value:
        return "0"

    return f"https://{value.lstrip('/')}"


def normalize_season_start_value(raw: object, *, default_starts: Sequence[int]) -> tuple[str, tuple[int, ...]]:
    starts = parse_season_starts_or_default(raw, default=default_starts)
    return season_starts_csv(starts), starts


def build_app_settings_snapshot_defaults(core_settings_obj: Any, *, default_starts: Sequence[int], snapshot_cls: Any) -> Any:
    season_start_csv, season_start_values = normalize_season_start_value(
        getattr(core_settings_obj, "SEASON_START_GAME_NUMBER", None),
        default_starts=default_starts,
    )
    text_moderation_whitelist = normalize_text_moderation_whitelist(
        getattr(core_settings_obj, "TEXT_MODERATION_WHITELIST", "0"),
    )
    text_moderation_blacklist = normalize_text_moderation_blacklist(
        getattr(core_settings_obj, "TEXT_MODERATION_BLACKLIST", "0"),
    )
    return snapshot_cls(
        registration_enabled=getattr(core_settings_obj, "REGISTRATION_ENABLED"),
        rooms_can_create=getattr(core_settings_obj, "ROOMS_CAN_CREATE"),
        rooms_can_enter=getattr(core_settings_obj, "ROOMS_CAN_ENTER"),
        games_can_start=getattr(core_settings_obj, "GAMES_CAN_START"),
        streams_can_start=getattr(core_settings_obj, "STREAMS_CAN_START"),
        chat_open_enabled=getattr(core_settings_obj, "CHAT_OPEN_ENABLED"),
        chat_messages_enabled=getattr(core_settings_obj, "CHAT_MESSAGES_ENABLED", True),
        verification_restrictions=getattr(core_settings_obj, "VERIFICATION_RESTRICTIONS"),
        admin_banner_text=normalize_admin_banner_text(getattr(core_settings_obj, "ADMIN_BANNER_TEXT", "0")),
        admin_banner_link=normalize_admin_banner_link(getattr(core_settings_obj, "ADMIN_BANNER_LINK", "0")),
        rooms_limit_global=getattr(core_settings_obj, "ROOMS_LIMIT_GLOBAL"),
        rooms_limit_per_user=getattr(core_settings_obj, "ROOMS_LIMIT_PER_USER"),
        rooms_empty_ttl_seconds=getattr(core_settings_obj, "ROOMS_EMPTY_TTL_SECONDS"),
        rooms_single_ttl_minutes=getattr(core_settings_obj, "ROOMS_SINGLE_TTL_MINUTES"),
        season_start_game_number=season_start_csv,
        season_start_game_numbers=season_start_values,
        text_moderation_whitelist=text_moderation_whitelist,
        text_moderation_whitelist_words=parse_text_moderation_whitelist(text_moderation_whitelist),
        text_moderation_blacklist=text_moderation_blacklist,
        text_moderation_blacklist_words=parse_text_moderation_blacklist(text_moderation_blacklist),
        game_min_ready_players=getattr(core_settings_obj, "GAME_MIN_READY_PLAYERS"),
        role_pick_seconds=getattr(core_settings_obj, "ROLE_PICK_SECONDS"),
        mafia_talk_seconds=getattr(core_settings_obj, "MAFIA_TALK_SECONDS"),
        player_talk_seconds=getattr(core_settings_obj, "PLAYER_TALK_SECONDS"),
        player_talk_short_seconds=getattr(core_settings_obj, "PLAYER_TALK_SHORT_SECONDS"),
        player_foul_seconds=getattr(core_settings_obj, "PLAYER_FOUL_SECONDS"),
        night_action_seconds=getattr(core_settings_obj, "NIGHT_ACTION_SECONDS"),
        vote_seconds=getattr(core_settings_obj, "VOTE_SECONDS"),
        winks_limit=getattr(core_settings_obj, "WINKS_LIMIT"),
        knocks_limit=getattr(core_settings_obj, "KNOCKS_LIMIT"),
        wink_spot_chance_percent=getattr(core_settings_obj, "WINK_SPOT_CHANCE_PERCENT"),
    )


def build_app_settings_snapshot_from_row(row: Any, *, default_starts: Sequence[int], snapshot_cls: Any) -> Any:
    season_start_csv, season_start_values = normalize_season_start_value(
        getattr(row, "season_start_game_number", None),
        default_starts=default_starts,
    )
    text_moderation_whitelist = normalize_text_moderation_whitelist(
        getattr(row, "text_moderation_whitelist", "0"),
    )
    text_moderation_blacklist = normalize_text_moderation_blacklist(
        getattr(row, "text_moderation_blacklist", "0"),
    )
    return snapshot_cls(
        registration_enabled=bool(getattr(row, "registration_enabled")),
        rooms_can_create=bool(getattr(row, "rooms_can_create")),
        rooms_can_enter=bool(getattr(row, "rooms_can_enter")),
        games_can_start=bool(getattr(row, "games_can_start")),
        streams_can_start=bool(getattr(row, "streams_can_start")),
        chat_open_enabled=bool(getattr(row, "chat_open_enabled", True)),
        chat_messages_enabled=bool(getattr(row, "chat_messages_enabled", True)),
        verification_restrictions=bool(getattr(row, "verification_restrictions")),
        admin_banner_text=normalize_admin_banner_text(getattr(row, "admin_banner_text", "0")),
        admin_banner_link=normalize_admin_banner_link(getattr(row, "admin_banner_link", "0")),
        rooms_limit_global=int(getattr(row, "rooms_limit_global")),
        rooms_limit_per_user=int(getattr(row, "rooms_limit_per_user")),
        rooms_empty_ttl_seconds=int(getattr(row, "rooms_empty_ttl_seconds")),
        rooms_single_ttl_minutes=int(getattr(row, "rooms_single_ttl_minutes")),
        season_start_game_number=season_start_csv,
        season_start_game_numbers=season_start_values,
        text_moderation_whitelist=text_moderation_whitelist,
        text_moderation_whitelist_words=parse_text_moderation_whitelist(text_moderation_whitelist),
        text_moderation_blacklist=text_moderation_blacklist,
        text_moderation_blacklist_words=parse_text_moderation_blacklist(text_moderation_blacklist),
        game_min_ready_players=int(getattr(row, "game_min_ready_players")),
        role_pick_seconds=int(getattr(row, "role_pick_seconds")),
        mafia_talk_seconds=int(getattr(row, "mafia_talk_seconds")),
        player_talk_seconds=int(getattr(row, "player_talk_seconds")),
        player_talk_short_seconds=int(getattr(row, "player_talk_short_seconds")),
        player_foul_seconds=int(getattr(row, "player_foul_seconds")),
        night_action_seconds=int(getattr(row, "night_action_seconds")),
        vote_seconds=int(getattr(row, "vote_seconds")),
        winks_limit=int(getattr(row, "winks_limit")),
        knocks_limit=int(getattr(row, "knocks_limit")),
        wink_spot_chance_percent=int(getattr(row, "wink_spot_chance_percent")),
    )


def normalize_users_sort(sort_by: str | None) -> str:
    value = (sort_by or "").strip().lower()
    if value in USERS_SORT_ALLOWED:
        return value

    return USERS_SORT_DEFAULT


def normalize_moderation_users_sort(sort_by: str | None) -> str:
    value = normalize_users_sort(sort_by)
    if value in MODERATION_USERS_SORT_ALLOWED:
        return value

    return USERS_SORT_DEFAULT


def admin_username_sort_key(raw: Any) -> tuple[int, tuple[tuple[int, int, int], ...]]:
    text = sanitize_username_for_schema(raw).casefold()
    if not text:
        return 3, tuple()

    lead_group = 3
    chars: list[tuple[int, int, int]] = []
    for ch in text:
        if ch in _RU_ALPHA_ORDER:
            group = 0
            order = _RU_ALPHA_ORDER[ch]
        elif ch in _EN_ALPHA_ORDER:
            group = 1
            order = _EN_ALPHA_ORDER[ch]
        else:
            group = 2
            order = ord(ch)

        if lead_group == 3:
            lead_group = group
        chars.append((group, order, ord(ch)))

    return lead_group, tuple(chars)


def admin_role_sort_key(role: Any) -> tuple[int, str]:
    return admin_users_role_sort_value(role)


async def fetch_friends_count_for_users(session: AsyncSession, ids: list[int]) -> dict[int, int]:
    friends_count: dict[int, int] = {uid: 0 for uid in ids}
    if not ids:
        return friends_count

    friend_rows = await session.execute(
        select(FriendLink.requester_id, FriendLink.addressee_id).where(
            FriendLink.status == "accepted",
            or_(FriendLink.requester_id.in_(ids), FriendLink.addressee_id.in_(ids)),
        )
    )
    for requester_id, addressee_id in friend_rows.all():
        try:
            requester_uid = int(requester_id)
        except Exception:
            requester_uid = 0
        try:
            addressee_uid = int(addressee_id)
        except Exception:
            addressee_uid = 0
        if requester_uid in friends_count:
            friends_count[requester_uid] += 1
        if addressee_uid in friends_count:
            friends_count[addressee_uid] += 1

    return friends_count


async def fetch_sanction_counts_for_users(session: AsyncSession, ids: list[int]) -> dict[int, dict[str, int]]:
    out: dict[int, dict[str, int]] = {uid: {SANCTION_TIMEOUT: 0, SANCTION_BAN: 0, SANCTION_SUSPEND: 0} for uid in ids}
    if not ids:
        return out

    rows = await session.execute(
        select(UserSanction.user_id, UserSanction.kind, func.count(UserSanction.id))
        .where(UserSanction.user_id.in_(ids), UserSanction.kind.in_([SANCTION_TIMEOUT, SANCTION_BAN, SANCTION_SUSPEND]))
        .group_by(UserSanction.user_id, UserSanction.kind)
    )
    for user_id, kind, cnt in rows.all():
        try:
            uid = int(user_id)
        except Exception:
            continue
        if uid not in out:
            continue
        kind_key = str(kind)
        if kind_key not in out[uid]:
            continue
        try:
            out[uid][kind_key] = int(cnt or 0)
        except Exception:
            out[uid][kind_key] = 0

    return out


def user_sort_metric(
    *,
    sort_by: str,
    uid: int,
    tg_invites_enabled: dict[int, bool],
    friends_count: dict[int, int],
    rooms_created: dict[int, int],
    room_seconds: dict[int, int],
    stream_seconds: dict[int, int],
    games_played: dict[int, int],
    games_hosted: dict[int, int],
    spectator_seconds: dict[int, int],
    sanction_counts: dict[int, dict[str, int]],
    last_game_at_ts: dict[int, int],
    last_room_id: dict[int, int | None],
    last_spectator_room_id: dict[int, int | None],
) -> int:
    if sort_by == "last_game_at":
        return last_game_at_ts.get(uid, 0)

    if sort_by == "last_room_id":
        return int(last_room_id.get(uid) or 0)

    if sort_by == "last_spectator_room_id":
        return int(last_spectator_room_id.get(uid) or 0)

    if sort_by == "tg_invites_enabled":
        return 1 if tg_invites_enabled.get(uid, True) is False else 0

    if sort_by == "friends_count":
        return friends_count.get(uid, 0)

    if sort_by == "rooms_created":
        return rooms_created.get(uid, 0)

    if sort_by == "room_minutes":
        return room_seconds.get(uid, 0) // 60

    if sort_by == "stream_minutes":
        return stream_seconds.get(uid, 0) // 60

    if sort_by == "games_played":
        return games_played.get(uid, 0)

    if sort_by == "games_hosted":
        return games_hosted.get(uid, 0)

    if sort_by == "spectator_minutes":
        return spectator_seconds.get(uid, 0) // 60

    if sort_by == "timeouts_count":
        return (sanction_counts.get(uid) or {}).get(SANCTION_TIMEOUT, 0)

    if sort_by == "bans_count":
        return (sanction_counts.get(uid) or {}).get(SANCTION_BAN, 0)

    if sort_by == "suspends_count":
        return (sanction_counts.get(uid) or {}).get(SANCTION_SUSPEND, 0)

    return 0


def moderation_user_sort_metric(*, sort_by: str, uid: int, sanction_counts: dict[int, dict[str, int]], last_game_at_ts: dict[int, int]) -> int:
    if sort_by == "last_game_at":
        return last_game_at_ts.get(uid, 0)

    if sort_by == "timeouts_count":
        return (sanction_counts.get(uid) or {}).get(SANCTION_TIMEOUT, 0)

    if sort_by == "bans_count":
        return (sanction_counts.get(uid) or {}).get(SANCTION_BAN, 0)

    if sort_by == "suspends_count":
        return (sanction_counts.get(uid) or {}).get(SANCTION_SUSPEND, 0)

    return 0


def compute_duration_seconds(months: int, days: int, hours: int, minutes: int) -> int:
    total_minutes = (max(0, months) * 30 * 24 * 60) + (max(0, days) * 24 * 60) + (max(0, hours) * 60) + max(0, minutes)
    return total_minutes * 60


def is_sanction_active(sanction: UserSanction, now: datetime | None = None) -> bool:
    if sanction.revoked_at is not None:
        return False

    now = now or datetime.now(timezone.utc)
    if sanction.expires_at and sanction.expires_at <= now:
        return False

    return True


def _empty_active_sanctions() -> dict[str, Optional[UserSanction]]:
    return {
        SANCTION_TIMEOUT: None,
        SANCTION_BAN: None,
        SANCTION_SUSPEND: None,
    }


def pick_active_sanction_kind(active: dict[str, Optional[UserSanction]]) -> str | None:
    for kind in (SANCTION_BAN, SANCTION_TIMEOUT, SANCTION_SUSPEND):
        if active.get(kind):
            return kind

    return None


async def fetch_active_sanction(session: AsyncSession, user_id: int, kind: str) -> Optional[UserSanction]:
    now = datetime.now(timezone.utc)
    rows = await session.execute(
        select(UserSanction)
        .where(
            UserSanction.user_id == int(user_id),
            UserSanction.kind == kind,
            UserSanction.revoked_at.is_(None),
            or_(UserSanction.expires_at.is_(None), UserSanction.expires_at > now),
        )
        .order_by(UserSanction.issued_at.desc(), UserSanction.id.desc())
        .limit(1)
    )

    return rows.scalars().first()


async def fetch_active_sanctions(session: AsyncSession, user_id: int) -> dict[str, Optional[UserSanction]]:
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
    out = _empty_active_sanctions()
    for row in items:
        if row.kind in out and out[row.kind] is None:
            out[row.kind] = row

    return out


async def fetch_active_sanctions_for_users(session: AsyncSession, user_ids: Iterable[int]) -> dict[int, dict[str, Optional[UserSanction]]]:
    ids = [int(x) for x in user_ids]
    out = {uid: _empty_active_sanctions() for uid in ids}
    if not ids:
        return out

    now = datetime.now(timezone.utc)
    rows = await session.execute(
        select(UserSanction)
        .where(
            UserSanction.user_id.in_(ids),
            UserSanction.kind.in_([SANCTION_TIMEOUT, SANCTION_BAN, SANCTION_SUSPEND]),
            UserSanction.revoked_at.is_(None),
            or_(UserSanction.expires_at.is_(None), UserSanction.expires_at > now),
        )
        .order_by(UserSanction.user_id.asc(), UserSanction.issued_at.desc(), UserSanction.id.desc())
    )
    for row in rows.scalars().all():
        uid = cast(int, row.user_id)
        if uid not in out:
            continue
        if row.kind in out[uid] and out[uid][row.kind] is None:
            out[uid][row.kind] = row

    return out


async def fetch_active_sanctions_by_telegram(session: AsyncSession, telegram_id: int) -> dict[str, Optional[UserSanction]]:
    tg_id = int(telegram_id or 0)
    out = _empty_active_sanctions()
    if tg_id <= 0:
        return out

    now = datetime.now(timezone.utc)
    rows = await session.execute(
        select(UserSanction)
        .where(
            UserSanction.telegram_id_snapshot == tg_id,
            UserSanction.revoked_at.is_(None),
            or_(UserSanction.expires_at.is_(None), UserSanction.expires_at > now),
        )
        .order_by(UserSanction.issued_at.desc(), UserSanction.id.desc())
    )
    for row in rows.scalars().all():
        if row.kind in out and out[row.kind] is None:
            out[row.kind] = row

    return out


async def fetch_sanctions_for_users(session: AsyncSession, user_ids: Iterable[int]) -> dict[int, list[UserSanction]]:
    ids = [int(x) for x in user_ids]
    if not ids:
        return {}

    rows = await session.execute(
        select(UserSanction)
        .where(UserSanction.user_id.in_(ids))
        .order_by(UserSanction.issued_at.desc(), UserSanction.id.desc())
    )
    out: dict[int, list[UserSanction]] = {}
    for row in rows.scalars().all():
        uid = cast(int, row.user_id)
        out.setdefault(uid, []).append(row)

    return out


def build_admin_sanction_out(row: UserSanction) -> AdminSanctionOut:
    from ..schemas.admin import AdminSanctionOut

    sid = cast(int, row.id)
    issued_by_id = cast(int, row.issued_by_id) if row.issued_by_id is not None else None
    revoked_by_id = cast(int, row.revoked_by_id) if row.revoked_by_id is not None else None
    return AdminSanctionOut(
        id=sid,
        kind=str(row.kind),
        reason=row.reason or None,
        issued_at=row.issued_at,
        issued_by_id=issued_by_id,
        issued_by_name=row.issued_by_name,
        duration_seconds=row.duration_seconds,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        revoked_by_id=revoked_by_id,
        revoked_by_name=row.revoked_by_name,
    )


def is_sanction_expired_after_game(row: UserSanction) -> bool:
    revoked_by_name = str(row.revoked_by_name or "").strip().lower()
    return (
        row.revoked_at is not None
        and str(row.kind or "").strip().lower() == SANCTION_SUSPEND
        and row.revoked_by_id is None
        and revoked_by_name == "проведение игры"
    )


def sanction_status(row: UserSanction, now: datetime) -> str:
    if row.revoked_at is not None:
        if is_sanction_expired_after_game(row):
            return "expired_auto"

        return "revoked"

    if row.expires_at is not None and row.expires_at <= now:
        return "expired_auto"

    return "active"


def sanction_finished_at(row: UserSanction) -> datetime | None:
    if row.revoked_at is not None:
        return row.revoked_at

    return row.expires_at


def sanction_served_seconds(row: UserSanction, now: datetime) -> int:
    end_at = row.revoked_at
    if end_at is None:
        if row.expires_at is not None and row.expires_at <= now:
            end_at = row.expires_at
        else:
            end_at = now

    return max(0, int((end_at - row.issued_at).total_seconds()))


def sanction_actor_display(name: str | None, user_id: int | None, *, auto_fallback: bool = False) -> str:
    normalized_name = str(name or "").strip()
    if normalized_name:
        return normalized_name

    if user_id is not None:
        return f"#{int(user_id)}"

    return "авто" if auto_fallback else "-"


async def revoke_active_suspend(session: AsyncSession, sanction: UserSanction, *, revoked_by_id: int | None, revoked_by_name: str | None, note_text: str, note_title: str = "Ограничение снято", chat_notice_source: str = "admin",) -> Notif:
    now = datetime.now(timezone.utc)
    uid = cast(int, sanction.user_id)
    remaining_duration_label = None
    if sanction.expires_at is not None:
        remaining_seconds = int((sanction.expires_at - now).total_seconds())
        if remaining_seconds > 0:
            remaining_duration_label = format_duration_seconds_compact(remaining_seconds)

    sanction.revoked_at = now
    sanction.revoked_by_id = int(revoked_by_id) if revoked_by_id is not None else None
    sanction.revoked_by_name = (revoked_by_name or "").strip() or None

    note = Notif(
        user_id=uid,
        title=note_title,
        text=note_text,
    )
    session.add(note)
    await session.commit()
    await session.refresh(note)

    with suppress(Exception):
        await emit_notify(uid, note, kind="sanction")
    with suppress(Exception):
        await maybe_send_sanction_telegram_if_offline(session, user_id=uid, note=note)
    with suppress(Exception):
        await emit_sanctions_update(session, uid)
    with suppress(Exception):
        from ..services.global_chat import emit_global_chat_sanction_removed_notice

        await emit_global_chat_sanction_removed_notice(
            session,
            actor_user_id=int(revoked_by_id) if revoked_by_id is not None else cast(int, sanction.issued_by_id),
            target_user_id=uid,
            target_username=None,
            kind=str(sanction.kind or ""),
            reason=str(sanction.reason or ""),
            source=chat_notice_source,
            remaining_duration_label=remaining_duration_label,
        )

    return note


async def reduce_suspend_after_hosted_game(session: AsyncSession, user_id: int, *, reduction_seconds: int = HOSTED_GAME_SUSPEND_REDUCTION_SECONDS) -> tuple[bool, bool, datetime | None]:
    active = await fetch_active_sanction(session, int(user_id), SANCTION_SUSPEND)
    if not active or active.expires_at is None:
        return False, False, None

    now = datetime.now(timezone.utc)
    next_expires_at = active.expires_at - timedelta(seconds=max(0, int(reduction_seconds)))
    if next_expires_at <= now:
        await revoke_active_suspend(
            session,
            active,
            revoked_by_id=None,
            revoked_by_name="проведение игры",
            note_text="Отстранение от игр снято автоматически после проведения игры.",
            chat_notice_source="game",
        )
        return True, True, None

    active.expires_at = next_expires_at
    await session.commit()
    with suppress(Exception):
        await emit_sanctions_update(session, int(user_id))

    return True, False, next_expires_at


def format_duration_parts(months: int, days: int, hours: int, minutes: int) -> str:
    parts: list[str] = []
    if months:
        parts.append(f"{months} мес")
    if days:
        parts.append(f"{days} д")
    if hours:
        parts.append(f"{hours} ч")
    if minutes or not parts:
        parts.append(f"{minutes} мин")

    return " ".join(parts)


def format_duration_seconds_compact(total_seconds: int) -> str:
    seconds_value = max(0, int(total_seconds or 0))
    if seconds_value <= 0:
        return "0 мин"

    total_minutes = (seconds_value + 59) // 60
    minutes_in_month = 30 * 24 * 60
    minutes_in_day = 24 * 60
    months, remainder = divmod(total_minutes, minutes_in_month)
    days, remainder = divmod(remainder, minutes_in_day)
    hours, minutes = divmod(remainder, 60)
    return format_duration_parts(months, days, hours, minutes)


def normalize_username(raw: str) -> str:
    out = unicodedata.normalize("NFKC", raw or "").strip()
    if not BOT_USERNAME_RE.match(out):
        raise HTTPException(status_code=422, detail="invalid_username_format")

    return out


def normalize_chat_mention_query(raw: str) -> str:
    out = unicodedata.normalize("NFKC", raw or "").strip()
    if not CHAT_MENTION_QUERY_RE.match(out):
        raise HTTPException(status_code=422, detail="invalid_mention_query")

    return out


def normalize_username_search_term(raw: str) -> str:
    return unicodedata.normalize("NFKC", raw or "").strip().lower()


def is_within_single_typo(candidate: str, query: str) -> bool:
    left = normalize_username_search_term(candidate)
    right = normalize_username_search_term(query)
    if not left or not right:
        return False

    if left == right:
        return True

    if len(left) == len(right):
        mismatches = [idx for idx, (left_ch, right_ch) in enumerate(zip(left, right)) if left_ch != right_ch]
        if (
            len(mismatches) == 2
            and mismatches[1] == mismatches[0] + 1
        ):
            idx = mismatches[0]
            if left[idx] == right[idx + 1] and left[idx + 1] == right[idx]:
                return True

    len_diff = len(left) - len(right)
    if abs(len_diff) > 1:
        return False

    if len(left) < len(right):
        left, right = right, left

    left_len = len(left)
    right_len = len(right)
    left_idx = 0
    right_idx = 0
    edits = 0

    while left_idx < left_len and right_idx < right_len:
        if left[left_idx] == right[right_idx]:
            left_idx += 1
            right_idx += 1
            continue

        edits += 1
        if edits > 1:
            return False

        if left_len == right_len:
            left_idx += 1
            right_idx += 1
        else:
            left_idx += 1

    if left_idx < left_len or right_idx < right_len:
        edits += 1

    return edits <= 1


async def find_user_ids_by_username_search(session: AsyncSession, username: str, *, include_deleted: bool = True) -> list[int]:
    needle = normalize_username_search_term(username)
    if not needle:
        return []

    filters = []
    if not include_deleted:
        filters.append(User.deleted_at.is_(None))

    exact_rows = await session.execute(
        select(User.id)
        .where(*filters, func.lower(User.username).contains(needle, autoescape=True))
        .order_by(User.id.desc())
    )
    exact_ids = [int(row_id) for row_id in exact_rows.scalars().all()]
    if exact_ids:
        return exact_ids

    if len(needle) < 3:
        return []

    candidate_rows = await session.execute(select(User.id, User.username).where(*filters))
    fuzzy_ids: list[int] = []
    for user_id, candidate_username in candidate_rows.all():
        if candidate_username and is_within_single_typo(str(candidate_username), needle):
            fuzzy_ids.append(int(user_id))

    return fuzzy_ids


def normalize_password(raw: str, *, allow_whitespace: bool = False) -> str:
    pwd = str(raw or "")
    if not pwd.strip():
        raise HTTPException(status_code=422, detail="invalid_password")

    if len(pwd) < 8 or len(pwd) > 32:
        raise HTTPException(status_code=422, detail="invalid_password")

    if PWD_CTRL_RE.search(pwd):
        raise HTTPException(status_code=422, detail="invalid_password")

    if not allow_whitespace and PWD_WS_RE.search(pwd):
        raise HTTPException(status_code=422, detail="invalid_password")

    return pwd


async def find_user_by_username(db: AsyncSession, username: str) -> User | None:
    stmt = select(User).where(func.lower(User.username) == username.lower())
    return (await db.execute(stmt)).scalar_one_or_none()


async def generate_user_id(db: AsyncSession) -> int:
    for _ in range(8):
        candidate = secrets.randbelow(9_999_999_999 - 10_000_000 + 1) + 10_000_000
        exists_row = await db.scalar(select(1).where(User.id == candidate).limit(1))
        if not exists_row:
            return candidate

    raise HTTPException(status_code=500, detail="id_generation_failed")


async def init_updates_read(db: AsyncSession, user_id: int) -> None:
    try:
        rows = await db.execute(select(SiteUpdate.id))
        ids = [int(r[0]) for r in rows.all() if r and r[0] is not None]
        if ids:
            now = datetime.now(timezone.utc)
            values = [{"user_id": user_id, "update_id": upd_id, "read_at": now} for upd_id in ids]
            stmt = insert(UpdateRead).values(values)
            stmt = stmt.on_conflict_do_nothing(index_elements=["user_id", "update_id"])
            await db.execute(stmt)
            await db.commit()
    except Exception:
        await db.rollback()


def require_bot_token(x_bot_token: str = Header(default="")) -> None:
    secret = settings.BOT_API_TOKEN or settings.TG_BOT_TOKEN
    if not x_bot_token or x_bot_token != secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="bot_forbidden")


async def emit_sanctions_update(session: AsyncSession, user_id: int) -> None:
    active = await fetch_active_sanctions(session, user_id)
    timeout = active.get(SANCTION_TIMEOUT)
    ban = active.get(SANCTION_BAN)
    suspend = active.get(SANCTION_SUSPEND)
    timeout_expires_at = cast(Optional[datetime], timeout.expires_at) if timeout else None
    suspend_expires_at = cast(Optional[datetime], suspend.expires_at) if suspend else None
    timeout_ts = int(timeout_expires_at.timestamp()) if timeout_expires_at else 0
    suspend_ts = int(suspend_expires_at.timestamp()) if suspend_expires_at else 0
    ban_active = bool(ban)
    state_key = f"user:{int(user_id)}:sanctions_state"
    try:
        await get_redis().hset(
            state_key,
            mapping={
                "ban_active": "1" if ban_active else "0",
                "timeout_expires_at": str(timeout_ts),
                "suspend_expires_at": str(suspend_ts),
            },
        )
    except Exception:
        pass
    payload = {
        "timeout_until": timeout_expires_at.isoformat() if timeout_expires_at else None,
        "ban_active": ban_active,
        "suspend_until": suspend_expires_at.isoformat() if suspend_expires_at else None,
    }
    await sio.emit("sanctions_update", payload, room=f"user:{user_id}", namespace="/auth")
    with suppress(Exception):
        from ..services.global_chat import emit_global_chat_permissions_updated
        await emit_global_chat_permissions_updated(int(user_id))


async def build_user_out_payload(session: AsyncSession, *, user_id: int, role: str | None = None):
    from ..schemas.user import UserOut
    from ..services.global_chat import count_global_chat_unread

    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    uid = cast(int, user.id)
    normalized_role = str(role or user.role or "")
    defaults_changed = await ensure_profile_theme_defaults(session, uid)
    if defaults_changed:
        await session.commit()
    theme_state = await resolve_profile_theme_state(session, uid)
    await write_user_profile_cache(
        uid,
        username=str(user.username),
        role=normalized_role,
        avatar_name=user.avatar_name,
        theme_color=theme_state.color,
        theme_until=theme_state.subscription_until,
        theme_icon=theme_state.icon,
    )
    if defaults_changed:
        with suppress(Exception):
            await emit_room_profile_theme_sync(uid, theme_state.color, theme_state.icon)
        with suppress(Exception):
            from ..services.global_chat import emit_global_chat_profile_theme_sync
            await emit_global_chat_profile_theme_sync(uid, theme_state.color, theme_state.icon)
    active = await fetch_active_sanctions(session, uid)
    timeout = active.get(SANCTION_TIMEOUT)
    ban = active.get(SANCTION_BAN)
    suspend = active.get(SANCTION_SUSPEND)
    in_active_game_as_alive_player = await is_user_in_active_alive_game(uid)
    in_active_game_as_player = await is_user_in_active_game(uid, scan_if_missing=True)
    chat_unread_count = await count_global_chat_unread(session, user_id=uid)

    return UserOut(
        id=uid,
        username=user.username,
        avatar_name=user.avatar_name,
        role=normalized_role,
        registered_at=user.registered_at,
        telegram_verified=bool(user.telegram_id),
        has_password=bool(user.password_hash),
        password_temp=bool(user.password_temp),
        protected_user=is_protected_admin(uid),
        hotkeys_visible=bool(user.hotkeys_visible),
        tg_invites_enabled=bool(user.tg_invites_enabled),
        subscription_active=theme_state.subscription_active,
        subscription_started_at=theme_state.subscription_started_at,
        subscription_until=theme_state.subscription_until,
        profile_theme_color=theme_state.color,
        profile_theme_icon=theme_state.icon,
        timeout_until=timeout.expires_at if timeout else None,
        suspend_until=suspend.expires_at if suspend else None,
        ban_active=bool(ban),
        in_active_game_as_alive_player=in_active_game_as_alive_player,
        in_active_game_as_player=in_active_game_as_player,
        chat_unread_count=chat_unread_count,
    )


async def emit_auth_profile_sync(user_id: int, *, role: str | None = None) -> None:
    uid = int(user_id)
    if uid <= 0:
        return

    async with SessionLocal() as session:
        payload = await build_user_out_payload(session, user_id=uid, role=role)

    await sio.emit(
        "profile_sync",
        payload.model_dump(mode="json"),
        room=f"user:{uid}",
        namespace="/auth",
    )


def _expired_subscription_sync_key(user_id: int, ends_at: datetime) -> str:
    normalized = _subscription_datetime_as_utc(ends_at)
    return f"user:{int(user_id)}:subscription_expired_sync:{int(normalized.timestamp())}"


def _subscription_expiring_soon_notice_key(user_id: int, ends_at: datetime) -> str:
    normalized = _subscription_datetime_as_utc(ends_at)
    return f"user:{int(user_id)}:subscription_expiring_soon:{int(normalized.timestamp())}"


def _subscription_datetime_as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _subscription_expiring_soon_notice_window(now: datetime) -> tuple[datetime, datetime]:
    local_now = (
        now.astimezone()
        if now.tzinfo is not None
        else now.replace(tzinfo=timezone.utc).astimezone()
    )
    target_start_local = (
        local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        + SUBSCRIPTION_EXPIRING_SOON_NOTICE_BEFORE
    )
    target_end_local = target_start_local + timedelta(days=1)
    return target_start_local.astimezone(timezone.utc), target_end_local.astimezone(timezone.utc)


def format_subscription_until(ends_at: datetime) -> str:
    local_dt = ends_at.astimezone() if ends_at.tzinfo is not None else ends_at
    return local_dt.strftime("%d.%m.%Y в %H:%M")


async def notify_subscription_upsert(session: AsyncSession, user: User, subscription: UserSubscription, *, extended: bool) -> None:
    uid = int(user.id)
    until_text = format_subscription_until(subscription.ends_at)
    title = "Благодарим за поддержку платформы!"
    text = (
        f"Ваша подписка продлена до {until_text}."
        if extended
        else f"Ваша подписка активирована до {until_text}."
    )

    note = Notif(user_id=uid, title=title, text=text)
    try:
        session.add(note)
        await session.commit()
        await session.refresh(note)
    except Exception:
        with suppress(Exception):
            await session.rollback()
        raise

    await emit_notify(uid, note, kind="subscription")

    telegram_id = int(user.telegram_id or 0)
    if telegram_id <= 0:
        return

    send_result = await send_text_message(chat_id=telegram_id, text=f"{title}\n\n{text}")
    if not send_result.ok:
        log.warning(
            "subscription.telegram_notify_failed",
            uid=uid,
            reason=send_result.reason,
        )


async def maybe_send_sanction_telegram_if_offline(session: AsyncSession, *, user_id: int, note: Notif, telegram_id: int | None = None) -> bool:
    # uid = int(user_id or 0)
    # if uid <= 0:
    #     return False
    #
    # tg_id = int(telegram_id or 0)
    # if tg_id <= 0:
    #     user = await session.get(User, uid)
    #     if not user or user.deleted_at is not None:
    #         return False
    #
    #     tg_id = int(user.telegram_id or 0)
    #     if tg_id <= 0:
    #         return False
    #
    # try:
    #     r = get_redis()
    #     base_online_ids = set(await fetch_online_user_ids(r))
    #     online_ids = await fetch_effective_online_user_ids(r, [uid], base_online_ids=base_online_ids)
    # except Exception:
    #     log.warning("sanction.telegram_presence_check_failed", uid=uid, exc_info=True)
    #     return False
    #
    # if uid in online_ids:
    #     return False
    #
    # try:
    #     send_result = await send_text_message(chat_id=tg_id, text=f"{note.title}\n\n{note.text}")
    # except Exception:
    #     log.warning("sanction.telegram_notify_failed", uid=uid, reason="unexpected_error", exc_info=True)
    #     return False
    #
    # if not send_result.ok:
    #     log.warning("sanction.telegram_notify_failed", uid=uid, reason=send_result.reason)
    #     return False
    #
    # return True

    # Sanction-related Telegram notifications are intentionally disabled.
    return False


async def _send_subscription_telegram_notice(session: AsyncSession, *, user_id: int, title: str, text: str) -> bool:
    uid = int(user_id)
    if uid <= 0:
        return False

    user = await session.get(User, uid)
    if not user or user.deleted_at is not None:
        return False

    telegram_id = int(user.telegram_id or 0)
    if telegram_id <= 0:
        return False

    try:
        send_result = await send_text_message(chat_id=telegram_id, text=f"{title}\n\n{text}")
    except Exception:
        log.warning("subscription.telegram_notify_failed", uid=uid, reason="unexpected_error", exc_info=True)
        return False

    if not send_result.ok:
        log.warning("subscription.telegram_notify_failed", uid=uid, reason=send_result.reason)
        return False

    return True


async def _create_subscription_site_notice_once(session: AsyncSession, user_id: int, *, title: str, text: str, no_toast: bool) -> Notif | None:
    uid = int(user_id)
    existing_note_id = await session.scalar(
        select(Notif.id)
        .where(
            Notif.user_id == uid,
            Notif.title == title,
            Notif.text == text,
        )
        .limit(1)
    )
    if existing_note_id:
        return None

    note = Notif(user_id=uid, title=title, text=text)
    session.add(note)
    await session.commit()
    await session.refresh(note)
    await emit_notify(uid, note, kind="subscription", no_toast=no_toast)
    return note


def _is_gif_avatar_name(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower().endswith(".gif")


async def delete_gif_avatar_for_inactive_subscription(session: AsyncSession, user_id: int, *, redis_client=None) -> bool:
    uid = int(user_id)
    if uid <= 0:
        return False

    row = await session.execute(select(User.avatar_name).where(User.id == uid))
    old_avatar_name = cast(str | None, row.scalar_one_or_none())
    if not _is_gif_avatar_name(old_avatar_name):
        return False

    await session.execute(
        update(User)
        .where(User.id == uid, User.avatar_name == old_avatar_name)
        .values(avatar_name=None)
    )
    await session.commit()

    await refresh_user_profile_cache(session, uid, redis_client=redis_client)
    with suppress(Exception):
        await invalidate_avatar_presign_cache(old_avatar_name, redis_client=redis_client)
    with suppress(Exception):
        await delete_avatars_async(uid)
    with suppress(Exception):
        await broadcast_creator_rooms(uid, avatar="delete")

    return True


async def sync_expired_profile_subscriptions() -> int:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(UserSubscription.user_id, UserSubscription.ends_at)
                .where(UserSubscription.ends_at <= now)
                .order_by(UserSubscription.ends_at.desc(), UserSubscription.user_id.asc())
            )
        ).all()
        if not rows:
            return 0

        r = get_redis()
        synced = 0
        for user_id_raw, ends_at in rows:
            try:
                uid = int(user_id_raw)
            except Exception:
                continue
            if uid <= 0 or not isinstance(ends_at, datetime):
                continue

            dedupe_key = _expired_subscription_sync_key(uid, ends_at)
            claimed = True
            try:
                claimed = bool(await r.set(dedupe_key, "1", ex=EXPIRED_SUBSCRIPTION_SYNC_TTL_S, nx=True))
            except Exception:
                claimed = True
            if not claimed:
                continue

            try:
                avatar_deleted = await delete_gif_avatar_for_inactive_subscription(session, uid, redis_client=r)
                if not avatar_deleted:
                    await refresh_user_profile_cache(session, uid, redis_client=r)
                await emit_auth_profile_sync(uid)
                await emit_room_profile_theme_sync(uid, None, None)
                with suppress(Exception):
                    from ..services.global_chat import emit_global_chat_profile_theme_sync
                    await emit_global_chat_profile_theme_sync(uid, None, None)
                created = await _create_subscription_site_notice_once(
                    session,
                    uid,
                    title="Подписка истекла",
                    text=f"Нам очень жаль, но Ваша подписка истекла.",
                    no_toast=False,
                )
                if created is not None:
                    await _send_subscription_telegram_notice(
                        session,
                        user_id=uid,
                        title="Подписка истекла",
                        text=f"Нам очень жаль, но Ваша подписка истекла.",
                    )
                synced += 1
            except Exception as exc:
                with suppress(Exception):
                    await session.rollback()
                with suppress(Exception):
                    await r.delete(dedupe_key)
                log.warning("subscriptions.expired_sync_failed", uid=uid, err=type(exc).__name__)

        return synced


async def notify_expiring_profile_subscriptions() -> int:
    now = datetime.now(timezone.utc)
    notice_start, notice_end = _subscription_expiring_soon_notice_window(now)

    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(UserSubscription.user_id, UserSubscription.ends_at)
                .join(User, User.id == UserSubscription.user_id)
                .where(
                    User.deleted_at.is_(None),
                    UserSubscription.starts_at <= now,
                    UserSubscription.ends_at > now,
                    UserSubscription.ends_at >= notice_start,
                    UserSubscription.ends_at < notice_end,
                )
                .order_by(UserSubscription.ends_at.asc(), UserSubscription.user_id.asc())
            )
        ).all()
        if not rows:
            return 0

        r = get_redis()
        notified = 0
        for user_id_raw, ends_at in rows:
            try:
                uid = int(user_id_raw)
            except Exception:
                continue
            if uid <= 0 or not isinstance(ends_at, datetime):
                continue

            dedupe_key = _subscription_expiring_soon_notice_key(uid, ends_at)
            claimed = True
            try:
                claimed = bool(
                    await r.set(
                        dedupe_key,
                        "1",
                        ex=SUBSCRIPTION_EXPIRING_SOON_NOTICE_TTL_S,
                        nx=True,
                    )
                )
            except Exception:
                claimed = True
            if not claimed:
                continue

            title = "Подписка скоро истечет"
            text = f"Ваша подписка истечет {format_subscription_until(ends_at)}."
            try:
                created = await _create_subscription_site_notice_once(
                    session,
                    uid,
                    title=title,
                    text=text,
                    no_toast=False,
                )
                if created is not None:
                    await _send_subscription_telegram_notice(
                        session,
                        user_id=uid,
                        title=title,
                        text=text,
                    )
                    notified += 1
            except Exception as exc:
                with suppress(Exception):
                    await session.rollback()
                with suppress(Exception):
                    await r.delete(dedupe_key)
                log.warning("subscriptions.expiring_soon_notify_failed", uid=uid, err=type(exc).__name__)

        return notified


def _expired_sanction_note(kind: str) -> tuple[str, str] | None:
    if kind == SANCTION_TIMEOUT:
        return "Таймаут завершен", "Срок вашего таймаута истек. Доступ к комнатам восстановлен."

    if kind == SANCTION_SUSPEND:
        return "Отстранение от игр снято", "Срок отстранения от игр истек."

    return None


async def _notify_expired_timed_sanctions(user_id: int) -> None:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        stmt = (
            select(UserSanction)
            .where(
                UserSanction.user_id == int(user_id),
                UserSanction.kind.in_(tuple(TIMED_KINDS)),
                UserSanction.revoked_at.is_(None),
                UserSanction.expires_at.is_not(None),
                UserSanction.expires_at <= now,
                UserSanction.expired_notified_at.is_(None),
            )
            .order_by(UserSanction.kind, UserSanction.expires_at.desc(), UserSanction.id.desc())
            .with_for_update(skip_locked=True)
        )
        rows = list((await session.scalars(stmt)).all())
        if not rows:
            return

        notes: list[Notif] = []
        chat_rows: list[UserSanction] = []
        notified_kinds: set[str] = set()
        for sanction in rows:
            kind = str(sanction.kind or "").strip()
            if kind in notified_kinds:
                sanction.expired_notified_at = now
                continue
            note_data = _expired_sanction_note(kind)
            if not note_data:
                continue
            notified_kinds.add(kind)
            sanction.expired_notified_at = now
            title, text = note_data
            note = Notif(user_id=int(user_id), title=title, text=text)
            session.add(note)
            notes.append(note)
            chat_rows.append(sanction)

        if not notes:
            return

        await session.commit()
        for note in notes:
            await session.refresh(note)
        for sanction in chat_rows:
            with suppress(Exception):
                await emit_expired_timed_sanction_chat_notice_once(session, sanction)

        for note in notes:
            with suppress(Exception):
                await emit_notify(int(user_id), note, kind="sanction")
            with suppress(Exception):
                await maybe_send_sanction_telegram_if_offline(session, user_id=int(user_id), note=note)


async def emit_expired_timed_sanction_chat_notice_once(session: AsyncSession, sanction: UserSanction) -> bool:
    sanction_id = int(getattr(sanction, "id", 0) or 0)
    user_id = int(getattr(sanction, "user_id", 0) or 0)
    if sanction_id <= 0 or user_id <= 0:
        return False

    redis_key = f"sanction:{sanction_id}:expired_chat_notice"
    use_redis_dedupe = True
    try:
        acquired = bool(
            await get_redis().set(
                redis_key,
                "1",
                ex=EXPIRED_SANCTION_CHAT_NOTICE_TTL_S,
                nx=True,
            )
        )
    except Exception:
        use_redis_dedupe = False
        acquired = True

    if not acquired:
        return False

    try:
        from ..services.global_chat import emit_global_chat_sanction_removed_notice

        payload = await emit_global_chat_sanction_removed_notice(
            session,
            actor_user_id=cast(int, sanction.issued_by_id),
            target_user_id=user_id,
            target_username=None,
            kind=str(sanction.kind or ""),
            reason=str(sanction.reason or ""),
            source="expired",
        )
        if payload is None:
            if use_redis_dedupe:
                with suppress(Exception):
                    await get_redis().delete(redis_key)
            return False

        return True

    except Exception:
        if use_redis_dedupe:
            with suppress(Exception):
                await get_redis().delete(redis_key)
        raise


async def emit_expired_timed_sanctions_chat_notices(*, batch_limit: int = 100) -> int:
    now = datetime.now(timezone.utc)
    emitted = 0
    async with SessionLocal() as session:
        stmt = (
            select(UserSanction)
            .where(
                UserSanction.kind.in_(tuple(TIMED_KINDS)),
                UserSanction.revoked_at.is_(None),
                UserSanction.expires_at.is_not(None),
                UserSanction.expires_at <= now,
                UserSanction.expired_notified_at.is_(None),
            )
            .order_by(UserSanction.expires_at.asc(), UserSanction.id.asc())
            .limit(max(1, int(batch_limit)))
        )
        rows = list((await session.scalars(stmt)).all())
        for sanction in rows:
            with suppress(Exception):
                if await emit_expired_timed_sanction_chat_notice_once(session, sanction):
                    emitted += 1

    return emitted


async def ensure_room_access_allowed(db: AsyncSession, user_id: int) -> None:
    from ..security.parameters import get_cached_settings

    active = await fetch_active_sanctions(db, int(user_id))
    if active.get(SANCTION_BAN):
        raise HTTPException(status_code=403, detail="user_banned")

    if active.get(SANCTION_TIMEOUT):
        raise HTTPException(status_code=403, detail="user_timeout")

    user = await db.get(User, int(user_id))
    if not user or user.deleted_at:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if get_cached_settings().verification_restrictions and not user.telegram_id:
        raise HTTPException(status_code=403, detail="not_verified")



async def ensure_profile_changes_allowed(db: AsyncSession, user_id: int) -> None:
    active = await fetch_active_sanctions(db, int(user_id))
    if active.get(SANCTION_BAN):
        raise HTTPException(status_code=403, detail="user_banned")


def is_protected_admin(user_id: int | str | None) -> bool:
    return is_protected_admin_uid(user_id)


def ensure_admin_target_allowed(user: User) -> None:
    if is_protected_admin(getattr(user, "id", 0)):
        raise HTTPException(status_code=403, detail="protected_user")


def ensure_admin_target_not_deleted(user: User) -> None:
    if getattr(user, "deleted_at", None) is not None:
        raise HTTPException(status_code=403, detail="user_deleted")


def ensure_moderation_target_allowed(user: User) -> None:
    if normalize_user_role(getattr(user, "role", None)) != ROLE_USER:
        raise HTTPException(status_code=403, detail="forbidden")

    if getattr(user, "deleted_at", None) is not None:
        raise HTTPException(status_code=403, detail="forbidden")


async def get_moderation_target_user(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    user = cast(User, user)
    ensure_moderation_target_allowed(user)
    return user


async def set_user_deleted(session: AsyncSession, user_id: int, *, deleted: bool) -> User:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    user = cast(User, user)
    uid = int(user.id)
    was_deleted = user.deleted_at is not None
    prev_avatar_name = cast(Optional[str], user.avatar_name)
    affected_friend_user_ids: tuple[int, ...] = ()
    subscription_deleted = False
    if deleted:
        _removed_friend_links, affected_friend_user_ids = await delete_friend_links_for_user(session, uid)
        active_subscription = await session.scalar(
            select(UserSubscription).where(UserSubscription.user_id == uid).limit(1)
        )
        if active_subscription is not None:
            await session.delete(active_subscription)
            subscription_deleted = True
        new_username = f"deleted_{uid}"
        user.username = new_username
        user.avatar_name = None
        user.telegram_id = None
    elif was_deleted:
        user.username = f"user_{uid}"

    if deleted:
        user.deleted_at = datetime.now(timezone.utc)
    else:
        user.deleted_at = None

    await session.commit()
    await session.refresh(user)

    with suppress(Exception):
        await refresh_user_profile_cache(session, uid)

    if deleted and subscription_deleted:
        with suppress(Exception):
            await emit_room_profile_theme_sync(uid, None, None)

    if deleted:
        with suppress(Exception):
            await invalidate_avatar_presign_cache(prev_avatar_name)

    if deleted:
        with suppress(Exception):
            await delete_avatars_async(uid)
        with suppress(Exception):
            await broadcast_creator_rooms(uid, update_name=user.username, avatar="delete")
        for other_user_id in affected_friend_user_ids:
            with suppress(Exception):
                await emit_friends_update(int(other_user_id), uid, "none")
    elif was_deleted:
        with suppress(Exception):
            await broadcast_creator_rooms(uid, update_name=user.username)

    with suppress(Exception):
        from ..services.global_chat import emit_global_chat_messages_refresh
        await emit_global_chat_messages_refresh()

    return user


async def delete_user_account_as_admin_action(session: AsyncSession, user_id: int, *, actor_user_id: int | None, actor_username: str | None, action: str = "admin_account_delete", details: str | None = None, note_title: str = "Аккаунт удален", note_text: str = "Ваш аккаунт был удален администратором.") -> User:
    target = await session.get(User, int(user_id))
    if not target:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(target)
    user = await set_user_deleted(session, int(user_id), deleted=True)
    uid = cast(int, user.id)

    if details is None:
        details = f"Удаление аккаунта user_id={uid}"
        if user.username:
            details += f" username={user.username}"

    await log_action(
        session,
        user_id=actor_user_id,
        username=actor_username,
        action=action,
        details=details,
        commit=False,
    )

    await session.commit()
    await force_logout_user(uid)
    return user


async def delete_friend_links_for_user(session: AsyncSession, user_id: int) -> tuple[int, tuple[int, ...]]:
    uid = int(user_id or 0)
    if uid <= 0:
        return 0, ()

    rows = await session.execute(select(FriendLink.requester_id, FriendLink.addressee_id).where(or_(FriendLink.requester_id == uid, FriendLink.addressee_id == uid)))
    friend_rows = rows.all()

    affected_user_ids: set[int] = set()
    for requester_id, addressee_id in friend_rows:
        try:
            requester_uid = int(requester_id)
        except Exception:
            requester_uid = 0
        try:
            addressee_uid = int(addressee_id)
        except Exception:
            addressee_uid = 0

        other_uid = addressee_uid if requester_uid == uid else requester_uid
        if other_uid > 0 and other_uid != uid:
            affected_user_ids.add(other_uid)

    await session.execute(delete(FriendLink).where(or_(FriendLink.requester_id == uid, FriendLink.addressee_id == uid)))
    removed_count = len(friend_rows)
    return removed_count, tuple(sorted(affected_user_ids))


async def force_logout_user(user_id: int) -> None:
    r = get_redis()
    try:
        sid = await r.get(f"user:{user_id}:sid")
    except Exception:
        sid = None
    if sid:
        try:
            await r.delete(f"session:{sid}:rjti")
            await r.delete(f"user:{user_id}:sid")
        except Exception:
            pass

    with suppress(Exception):
        await sio.emit("force_logout", {"reason": "account_deleted"}, room=f"user:{user_id}", namespace="/auth")
        await sio.emit("force_logout", {"reason": "account_deleted"}, room=f"user:{user_id}", namespace="/room")


async def _user_has_recorded_games(session: AsyncSession, user_id: int) -> bool:
    uid = int(user_id or 0)
    if uid <= 0:
        return False

    row = await session.scalar(
        select(1)
        .where(or_(Game.head_id == uid, Game.roles.has_key(str(uid))))
        .limit(1)
    )
    return bool(row)


async def _can_auto_delete_unverified_user(session: AsyncSession, user: User, *, cutoff_dt: datetime) -> bool:
    uid = int(getattr(user, "id", 0) or 0)
    if uid <= 0:
        return False

    if user.deleted_at is not None or user.telegram_id is not None:
        return False

    if str(user.role or "").strip().lower() != "user":
        return False

    if is_protected_admin(uid):
        return False

    if user.registered_at > cutoff_dt:
        return False

    if await _user_has_recorded_games(session, uid):
        return False

    return True


async def delete_stale_unverified_accounts(*, batch_limit: int = 100, min_age_minutes: int = 60) -> int:
    from ..security.parameters import get_cached_settings

    if not get_cached_settings().verification_restrictions:
        return 0

    limit = max(1, min(int(batch_limit), 1000))
    min_age = max(1, int(min_age_minutes))
    cutoff_dt = datetime.now(timezone.utc) - timedelta(minutes=min_age)
    deleted = 0

    async with SessionLocal() as session:
        stmt = (
            select(User)
            .where(
                User.deleted_at.is_(None),
                User.telegram_id.is_(None),
                User.role == "user",
                User.registered_at <= cutoff_dt,
            )
            .order_by(User.registered_at.asc(), User.id.asc())
            .limit(limit)
        )
        users = list((await session.scalars(stmt)).all())
        if not users:
            return 0

        for user in users:
            uid = int(getattr(user, "id", 0) or 0)
            if uid <= 0:
                continue

            redis_key = f"user:{uid}:auto_delete_unverified"
            use_redis_lock = True
            try:
                acquired = bool(
                    await get_redis().set(
                        redis_key,
                        "1",
                        ex=AUTO_DELETE_UNVERIFIED_ACCOUNT_LOCK_TTL_S,
                        nx=True,
                    )
                )
            except Exception:
                use_redis_lock = False
                acquired = True

            if not acquired:
                continue

            try:
                fresh_user = await session.get(User, uid, populate_existing=True)
                if not fresh_user or not await _can_auto_delete_unverified_user(session, fresh_user, cutoff_dt=cutoff_dt):
                    if use_redis_lock:
                        with suppress(Exception):
                            await get_redis().delete(redis_key)
                    continue

                details = (
                    "Автоматическое удаление неверифицированного аккаунта "
                    f"user_id={uid} username={fresh_user.username}"
                )
                await delete_user_account_as_admin_action(
                    session,
                    uid,
                    actor_user_id=None,
                    actor_username="system",
                    action="auto_unverified_account_delete",
                    details=details,
                    note_title="Аккаунт удален",
                    note_text=(
                        "Ваш аккаунт был удален автоматически: аккаунт не был "
                        "верифицирован в течение часа после регистрации."
                    ),
                )
                deleted += 1
            except Exception:
                with suppress(Exception):
                    await session.rollback()
                if use_redis_lock:
                    with suppress(Exception):
                        await get_redis().delete(redis_key)
                log.exception("users.auto_delete_unverified.failed", user_id=uid)

    return deleted


async def force_leave_user_from_rooms(user_id: int, *, reason: str) -> None:
    uid = int(user_id or 0)
    if uid <= 0:
        return

    from ..realtime.utils import find_user_rooms, cleanup_user_from_room

    r = get_redis()
    try:
        extra_rid = int(await r.get(f"user:{uid}:room") or 0)
    except Exception:
        extra_rid = 0

    try:
        rooms = await find_user_rooms(r, uid, current_rid=0, extra_rids=[extra_rid] if extra_rid > 0 else None)
    except Exception:
        log.exception("api.force_leave.find_rooms_failed", uid=uid, reason=reason)
        return

    if not rooms:
        return

    actor_username = f"user{uid}"
    for rid, was_member, was_spectator in rooms:
        with suppress(Exception):
            await sio.emit(
                "force_leave",
                {"room_id": int(rid), "reason": reason},
                room=f"user:{uid}",
                namespace="/room",
            )
        try:
            await cleanup_user_from_room(r, int(rid), uid, was_member=bool(was_member), was_spectator=bool(was_spectator), sid=None, actor_username=actor_username)
        except Exception:
            log.exception("api.force_leave.cleanup_failed", uid=uid, rid=rid, reason=reason)


def _parse_int(raw: Any) -> int:
    if raw is None:
        return 0

    if isinstance(raw, bytes):
        try:
            raw = raw.decode()
        except Exception:
            return 0

    try:
        return int(raw)

    except Exception:
        return 0


def safe_int(raw: Any) -> int:
    return _parse_int(raw)


def non_empty_str(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None

    out = raw.strip()
    return out or None


def normalizeGameActionsForUpdate(raw: object) -> list[object]:
    if not isinstance(raw, list):
        return []

    normalized: list[object] = []
    for item in raw:
        normalized.append(dict(item) if isinstance(item, dict) else item)
    return normalized


def gameActionHasPpk(rawAction: object) -> bool:
    if not isinstance(rawAction, dict):
        return False

    return bool(rawAction.get("ppk")) or str(rawAction.get("format") or "").strip().upper() == "PPK"


def findGamePpkTargetUserId(actions: list[object]) -> int | None:
    for rawAction in reversed(actions):
        if not isinstance(rawAction, dict):
            continue
        if str(rawAction.get("type") or "").strip().lower() != "death":
            continue
        if str(rawAction.get("reason") or "").strip().lower() != "foul":
            continue
        if not gameActionHasPpk(rawAction):
            continue
        targetUid = safe_int(rawAction.get("target_id"))
        if targetUid > 0:
            return targetUid

    for rawAction in reversed(actions):
        if not isinstance(rawAction, dict):
            continue
        if str(rawAction.get("type") or "").strip().lower() != "foul":
            continue
        if not gameActionHasPpk(rawAction):
            continue
        targetUid = safe_int(rawAction.get("target_id"))
        if targetUid > 0:
            return targetUid

    return None


def findGameFoulDeathActionIndex(actions: list[object], targetUid: int) -> int | None:
    if targetUid <= 0:
        return None

    for index, rawAction in enumerate(actions):
        if not isinstance(rawAction, dict):
            continue
        if str(rawAction.get("type") or "").strip().lower() != "death":
            continue
        if str(rawAction.get("reason") or "").strip().lower() != "foul":
            continue
        if safe_int(rawAction.get("target_id")) == targetUid:
            return index

    return None


def findGameFoulActionIndex(actions: list[object], targetUid: int) -> int | None:
    if targetUid <= 0:
        return None

    bestIndex: int | None = None
    bestCount = 0
    for index, rawAction in enumerate(actions):
        if not isinstance(rawAction, dict):
            continue
        if str(rawAction.get("type") or "").strip().lower() != "foul":
            continue
        if safe_int(rawAction.get("target_id")) != targetUid:
            continue
        foulCount = safe_int(rawAction.get("count"))
        if foulCount < 4:
            continue
        if bestIndex is None or foulCount >= bestCount:
            bestIndex = index
            bestCount = foulCount

    return bestIndex


def setGameActionPpk(rawAction: dict[str, Any], enabled: bool) -> None:
    if enabled:
        rawAction["ppk"] = True
        rawAction["format"] = "PPK"
        return

    rawAction.pop("ppk", None)
    if str(rawAction.get("format") or "").strip().upper() == "PPK":
        rawAction.pop("format", None)


def game_action_slot_label(uid_to_slot: dict[int, int], raw_uid: Any, *, head_uid: int = 0) -> str:
    uid = safe_int(raw_uid)
    if uid <= 0:
        return "-"

    slot = safe_int(uid_to_slot.get(uid))
    if slot > 0:
        return f"Слот {slot}"

    if 0 < head_uid == uid:
        return "Ведущий"

    return f"user{uid}"


def game_action_slot_labels(uid_to_slot: dict[int, int], raw_values: Any, *, head_uid: int = 0) -> list[str]:
    if not isinstance(raw_values, list):
        return []

    out: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        label = game_action_slot_label(uid_to_slot, raw_value, head_uid=head_uid)
        if label == "-" or label in seen:
            continue
        seen.add(label)
        out.append(label)
    return out


def game_action_join(values: list[str]) -> str:
    return ", ".join(values) if values else "-"


def game_action_role_label(raw_role: Any) -> str:
    role = str(raw_role or "").strip().lower()
    if role == "citizen":
        return "Мирный"

    if role == "sheriff":
        return "Шериф"

    if role == "mafia":
        return "Мафия"

    if role == "don":
        return "Дон"

    return role or "-"


def game_action_reason_label(raw_reason: Any) -> str:
    reason = str(raw_reason or "").strip().lower()
    if reason == "vote":
        return "Голосование"

    if reason == "night":
        return "Ночь"

    if reason == "foul":
        return "Фолы"

    if reason == "suicide":
        return "Самоубийство"

    return reason or "-"


def game_action_bool_label(raw_value: Any) -> str:
    return "Да" if bool(raw_value) else "Нет"


def game_action_vote_pairs(uid_to_slot: dict[int, int], raw_votes: Any, *, head_uid: int = 0) -> list[str]:
    if not isinstance(raw_votes, dict):
        return []

    out: list[str] = []
    for raw_target_uid, raw_voters in raw_votes.items():
        target_label = game_action_slot_label(uid_to_slot, raw_target_uid, head_uid=head_uid)
        if target_label == "-" or not isinstance(raw_voters, list):
            continue
        for raw_voter_uid in raw_voters:
            voter_label = game_action_slot_label(uid_to_slot, raw_voter_uid, head_uid=head_uid)
            if voter_label == "-":
                continue
            out.append(f"{voter_label} -> {target_label}")
    return out


def game_action_target_pairs(uid_to_slot: dict[int, int], raw_map: Any, *, head_uid: int = 0) -> list[str]:
    if not isinstance(raw_map, dict):
        return []

    out: list[str] = []
    for raw_actor_uid, raw_target_uid in raw_map.items():
        actor_label = game_action_slot_label(uid_to_slot, raw_actor_uid, head_uid=head_uid)
        target_label = game_action_slot_label(uid_to_slot, raw_target_uid, head_uid=head_uid)
        if actor_label == "-" or target_label == "-":
            continue
        out.append(f"{actor_label} -> {target_label}")
    return out


def game_action_wills(uid_to_slot: dict[int, int], raw_wills: Any, *, head_uid: int = 0) -> list[str]:
    if not isinstance(raw_wills, dict):
        return []

    out: list[str] = []
    for raw_target_uid, raw_verdict in raw_wills.items():
        target_label = game_action_slot_label(uid_to_slot, raw_target_uid, head_uid=head_uid)
        if target_label == "-":
            continue
        verdict = str(raw_verdict or "").strip().lower()
        if verdict == "citizen":
            verdict_label = "мирный"
        elif verdict == "mafia":
            verdict_label = "мафия"
        else:
            verdict_label = verdict or "-"
        out.append(f"{target_label}: {verdict_label}")
    return out


def game_action_check_result(checker_role: Any, target_role: Any) -> str:
    checker = str(checker_role or "").strip().lower()
    target = str(target_role or "").strip().lower()
    if checker == "sheriff":
        return "Мафия" if target in {"mafia", "don"} else "Мирный"

    if checker == "don":
        return "Шериф" if target == "sheriff" else "Мирный"

    return "-"


def game_action_fields(action: dict[str, Any], *, uid_to_slot: dict[int, int], head_uid: int) -> tuple[str, str, list[AdminGameActionFieldOut]]:
    from ..schemas.admin import AdminGameActionFieldOut

    action_type = str(action.get("type") or "").strip().lower()
    day = safe_int(action.get("day"))
    actor_label = game_action_slot_label(uid_to_slot, action.get("actor_id"), head_uid=head_uid)
    target_label = game_action_slot_label(uid_to_slot, action.get("target_id"), head_uid=head_uid)
    fields: list[AdminGameActionFieldOut] = []

    def add_field(label: str, value: str | None) -> None:
        if value is None:
            return

        value_text = str(value).strip()
        if not value_text:
            return

        fields.append(AdminGameActionFieldOut(label=label, value=value_text))

    if day > 0:
        add_field("День", str(day))

    if action_type == "foul":
        speech_label = game_action_slot_label(uid_to_slot, action.get("speech_uid"), head_uid=head_uid)
        is_ppk = bool(action.get("ppk")) or str(action.get("format") or "").strip().upper() == "PPK"
        if speech_label != "-":
            add_field("Этап", "Речь игрока")
        add_field("Кто поставил", actor_label)
        add_field("Кому", target_label)
        add_field("Количество фолов", str(max(0, safe_int(action.get("count")))))
        if speech_label != "-":
            add_field("На чьей речи", speech_label)
        add_field("ППК", game_action_bool_label(is_ppk))
        if is_ppk:
            add_field("Формат", "PPK")
        return "Фол", f"{actor_label} поставил фол игроку {target_label}", fields

    if action_type == "wink":
        add_field("Этап", "День / голосование")
        add_field("Кто подмигнул", actor_label)
        add_field("Кому", target_label)
        add_field("Кто-то увидел", game_action_bool_label(action.get("spotted")))
        return "Подмигивание", f"{actor_label} подмигнул игроку {target_label}", fields

    if action_type == "knock":
        add_field("Этап", "День / голосование")
        add_field("Кто стучал", actor_label)
        add_field("Кому", target_label)
        add_field("Количество стуков", str(max(0, safe_int(action.get("count")))))
        return "Стук", f"{actor_label} постучал игроку {target_label}", fields

    if action_type == "nominate":
        add_field("Этап", "День")
        add_field("Кто выставил", actor_label)
        add_field("Кого выставили", target_label)
        return "Выставление", f"{actor_label} выставил игрока {target_label}", fields

    if action_type == "vote":
        targets = game_action_slot_labels(uid_to_slot, action.get("targets"), head_uid=head_uid)
        is_lift = bool(action.get("lift"))
        add_field("Этап", "Голосование")
        add_field("Тип", "На поднятие" if is_lift else "Обычное")
        add_field("Цели", game_action_join(targets))
        if is_lift:
            voters = game_action_slot_labels(uid_to_slot, action.get("by"), head_uid=head_uid)
            add_field("Кто голосовал за поднятие", game_action_join(voters))
            return "Голосование", "Голосование на поднятие", fields

        vote_pairs = game_action_vote_pairs(uid_to_slot, action.get("votes"), head_uid=head_uid)
        add_field("Кто в кого голосовал", "; ".join(vote_pairs) if vote_pairs else "-")
        return "Голосование", "Обычное голосование", fields

    if action_type == "night_check":
        checker_role = str(action.get("checker_role") or "").strip().lower()
        target_role = str(action.get("target_role") or "").strip().lower()
        add_field("Этап", "Ночь")
        add_field("Кто проверял", actor_label)
        add_field("Кого проверяли", target_label)
        add_field("Роль проверяющего", game_action_role_label(checker_role))
        add_field("Реальная роль цели", game_action_role_label(target_role))
        add_field("Результат проверки", game_action_check_result(checker_role, target_role))
        return "Ночная проверка", f"{actor_label} проверил игрока {target_label}", fields

    if action_type == "night_shoot_result":
        shooters = game_action_slot_labels(uid_to_slot, action.get("shooters"), head_uid=head_uid)
        shot_pairs = game_action_target_pairs(uid_to_slot, action.get("shots"), head_uid=head_uid)
        kill_label = game_action_slot_label(uid_to_slot, action.get("kill_uid"), head_uid=head_uid)
        add_field("Этап", "Ночь")
        add_field("Кто стрелял", game_action_join(shooters))
        add_field("Выстрелы", "; ".join(shot_pairs) if shot_pairs else "-")
        add_field("Убитый", kill_label if kill_label != "-" else "Нет")
        add_field("Убийство прошло", game_action_bool_label(action.get("kill_ok")))
        return "Ночной отстрел", "Итог ночного отстрела", fields

    if action_type == "best_move":
        targets = game_action_slot_labels(uid_to_slot, action.get("targets"), head_uid=head_uid)
        add_field("Этап", "После ночи")
        add_field("Кто сделал лучший ход", actor_label)
        add_field("Отмеченные цели", game_action_join(targets))
        return "Лучший ход", f"{actor_label} отметил лучший ход", fields

    if action_type == "farewell":
        mode = str(action.get("mode") or "").strip().lower()
        wills = game_action_wills(uid_to_slot, action.get("wills"), head_uid=head_uid)
        mode_label = "После голосования" if mode == "voted" else "После ночи" if mode == "killed" else mode or "-"
        add_field("Этап", "Прощальная речь")
        add_field("Чье завещание", actor_label)
        add_field("Режим", mode_label)
        add_field("Завещание", "; ".join(wills) if wills else "-")
        return "Завещание", f"Завещание игрока {actor_label}", fields

    if action_type == "death":
        reason = str(action.get("reason") or "").strip().lower()
        by_labels = game_action_slot_labels(uid_to_slot, action.get("by"), head_uid=head_uid)
        is_ppk = bool(action.get("ppk")) or str(action.get("format") or "").strip().upper() == "PPK"
        if reason == "vote":
            add_field("Этап", "Голосование")
        elif reason == "night":
            add_field("Этап", "Ночь")
        elif reason == "foul":
            add_field("Этап", "Удаление по фолам")
        elif reason == "suicide":
            add_field("Этап", "Самоубийство")
        add_field("Кто выбыл", target_label)
        add_field("Причина", game_action_reason_label(reason))
        if by_labels:
            if reason == "vote":
                add_field("Кто голосовал", game_action_join(by_labels))
            elif reason == "night":
                add_field("Кто стрелял", game_action_join(by_labels))
            else:
                add_field("Кто участвовал", game_action_join(by_labels))
        add_field("ППК", game_action_bool_label(is_ppk))
        if is_ppk:
            add_field("Формат", "PPK")
        return "Выбытие", f"Выбыл игрок {target_label}", fields

    add_field("Сырые данные", str(action))
    return action_type or "Событие", f"Событие {action_type or 'unknown'}", fields


def normalize_game_result(raw: Any) -> str:
    result = str(raw or "").strip().lower()
    if result in ("red", "black", "draw"):
        return result

    return "draw"


def game_actions_has_ppk(raw_actions: Any) -> bool:
    if not isinstance(raw_actions, list):
        return False

    for raw_action in raw_actions:
        if not isinstance(raw_action, dict):
            continue
        action_type = str(raw_action.get("type") or "").strip().lower()
        if action_type not in {"death", "foul"}:
            continue
        if action_type == "death" and str(raw_action.get("reason") or "").strip().lower() != "foul":
            continue
        if bool(raw_action.get("ppk")) or str(raw_action.get("format") or "").strip().upper() == "PPK":
            return True

    return False


async def fetch_games_history_page(db: AsyncSession, *, page: int, per_page: int, player_uid: int | None = None, player_role: Literal["citizen", "mafia", "don", "sheriff"] | None = None) -> UserGamesHistoryOut:
    from ..schemas.user import UserGamesHistoryOut, GameHistoryItemOut, GameHistoryHostOut

    valid_roles = {"citizen", "mafia", "don", "sheriff"}
    per_page_i = max(1, min(safe_int(per_page), 100))
    page_num = max(1, min(int(page or 1), 1_000_000))
    uid_i = safe_int(player_uid)
    uid_key = str(uid_i) if uid_i > 0 else None
    role_filter_raw = str(player_role or "").strip().lower()
    role_filter = role_filter_raw if role_filter_raw in valid_roles else None

    total_stmt = select(func.count(Game.id))
    result_stmt = select(Game.result, func.count(Game.id)).group_by(Game.result)
    rows_stmt = (
        select(
            Game.id,
            Game.head_id,
            Game.result,
            Game.black_alive_at_finish,
            Game.started_at,
            Game.finished_at,
            Game.roles,
            Game.points,
            Game.mmr,
            Game.actions,
        )
        .order_by(Game.id.desc())
    )

    if uid_key is not None:
        filter_expr = Game.roles.has_key(uid_key)
        if role_filter is not None:
            filter_expr = and_(filter_expr, Game.roles.contains({uid_key: role_filter}))
        total_stmt = total_stmt.where(filter_expr)
        result_stmt = result_stmt.where(filter_expr)
        rows_stmt = rows_stmt.where(filter_expr)

    total = int(await db.scalar(total_stmt) or 0)
    pages = max(1, (total + per_page_i - 1) // per_page_i)
    if page_num > pages:
        page_num = pages
    offset = (page_num - 1) * per_page_i

    total_red_wins = 0
    total_black_wins = 0
    result_rows = await db.execute(result_stmt)
    for result_raw, count_raw in result_rows.all():
        cnt = max(0, safe_int(count_raw))
        normalized_result = normalize_game_result(result_raw)
        if normalized_result == "red":
            total_red_wins += cnt
        elif normalized_result == "black":
            total_black_wins += cnt

    rows = await db.execute(rows_stmt.offset(offset).limit(per_page_i))
    raw_games = rows.all()

    user_ids: set[int] = set()
    for _game_id, head_id, _result, _black_alive, _started, _finished, _roles, _points, _mmr, _actions in raw_games:
        hid = safe_int(head_id)
        if hid > 0:
            user_ids.add(hid)

    profiles = await get_user_profiles_cached(db, user_ids) if user_ids else {}

    items: list[GameHistoryItemOut] = []
    for game_id, head_id, result_raw, black_alive_raw, started_at, finished_at, roles_raw, points_raw, mmr_raw, actions_raw in raw_games:
        gid = safe_int(game_id)
        if gid <= 0:
            continue

        head_uid = safe_int(head_id)
        head_auto = head_uid <= 0
        head_profile = profiles.get(head_uid) if head_uid > 0 else None
        head_username = non_empty_str((head_profile or {}).get("username"))
        if head_username is None and head_uid > 0:
            head_username = f"user{head_uid}"
        head_avatar_name = non_empty_str((head_profile or {}).get("avatar_name"))

        try:
            duration_seconds = max(0, int((finished_at - started_at).total_seconds()))
        except Exception:
            duration_seconds = 0

        player_role_value: Literal["citizen", "mafia", "don", "sheriff"] | None = None
        player_points_value: int | None = None
        player_mmr_value: int | None = None
        if uid_key is not None and isinstance(roles_raw, dict):
            role_raw = str(roles_raw.get(uid_key) or "").strip().lower()
            if role_raw in valid_roles:
                player_role_value = cast(Literal["citizen", "mafia", "don", "sheriff"], role_raw)
            points_map = points_raw if isinstance(points_raw, dict) else {}
            mmr_map = mmr_raw if isinstance(mmr_raw, dict) else {}
            player_points_value = safe_int(points_map.get(uid_key, 0))
            player_mmr_value = safe_int(mmr_map.get(uid_key, 0))

        items.append(
            GameHistoryItemOut(
                id=gid,
                number=gid,
                head=GameHistoryHostOut(
                    id=head_uid if not head_auto else None,
                    username=head_username,
                    avatar_name=head_avatar_name,
                    auto=head_auto,
                ),
                result=normalize_game_result(result_raw),
                has_ppk=game_actions_has_ppk(actions_raw),
                player_role=player_role_value,
                player_points=player_points_value,
                player_mmr=player_mmr_value,
                black_alive_at_finish=max(0, safe_int(black_alive_raw)),
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration_seconds,
                slots=[],
            )
        )

    return UserGamesHistoryOut(
        total=total,
        page=page_num,
        pages=pages,
        per_page=per_page_i,
        total_red_wins=total_red_wins,
        total_black_wins=total_black_wins,
        items=items,
    )


async def check_sanctions_expired(user_id: int, *, throttle_s: int = 30) -> None:
    r = get_redis()
    if throttle_s > 0:
        try:
            ok = await r.set(f"user:{user_id}:sanctions_check", "1", ex=throttle_s, nx=True)
        except Exception:
            ok = True
        if not ok:
            return

    key = f"user:{user_id}:sanctions_state"
    try:
        prev = await r.hgetall(key)
    except Exception:
        return

    now_ts = int(time())
    prev_timeout_ts = _parse_int(prev.get("timeout_expires_at"))
    prev_suspend_ts = _parse_int(prev.get("suspend_expires_at"))
    prev_ban = 1 if _parse_int(prev.get("ban_active")) > 0 else 0
    next_timeout_ts = prev_timeout_ts if prev_timeout_ts > now_ts else 0
    next_suspend_ts = prev_suspend_ts if prev_suspend_ts > now_ts else 0
    if next_timeout_ts != prev_timeout_ts or next_suspend_ts != prev_suspend_ts:
        try:
            await r.hset(
                key,
                mapping={
                    "ban_active": "1" if prev_ban else "0",
                    "timeout_expires_at": str(next_timeout_ts),
                    "suspend_expires_at": str(next_suspend_ts),
                },
            )
        except Exception:
            pass

        payload = {
            "timeout_until": datetime.fromtimestamp(next_timeout_ts, tz=timezone.utc).isoformat() if next_timeout_ts else None,
            "ban_active": bool(prev_ban),
            "suspend_until": datetime.fromtimestamp(next_suspend_ts, tz=timezone.utc).isoformat() if next_suspend_ts else None,
        }
        with suppress(Exception):
            await sio.emit("sanctions_update", payload, room=f"user:{int(user_id)}", namespace="/auth")
        with suppress(Exception):
            from ..services.global_chat import emit_global_chat_permissions_updated
            await emit_global_chat_permissions_updated(int(user_id))

    try:
        await _notify_expired_timed_sanctions(int(user_id))
    except Exception:
        log.warning("sanctions.expired.notify_failed", user_id=int(user_id))


def serialize_game_for_redis(game_dict: Dict[str, Any]) -> Dict[str, str]:
    nominate_mode = str(game_dict.get("nominate_mode") or "players")
    if nominate_mode not in ("players", "head"):
        nominate_mode = "players"
    return {
        "mode": str(game_dict["mode"]),
        "format": str(game_dict["format"]),
        "spectators_limit": str(normalize_spectators_limit(game_dict.get("spectators_limit"))),
        "nominate_mode": nominate_mode,
        "break_at_zero": "1" if raw_bool(game_dict.get("break_at_zero"), True) else "0",
        "lift_at_zero": "1" if raw_bool(game_dict.get("lift_at_zero"), True) else "0",
        "lift_3x": "1" if raw_bool(game_dict.get("lift_3x"), True) else "0",
        "wink_knock": "1" if raw_bool(game_dict.get("wink_knock"), True) else "0",
        "farewell_wills": "1" if raw_bool(game_dict.get("farewell_wills"), True) else "0",
        "music": "1" if raw_bool(game_dict.get("music"), True) else "0",
    }


def raw_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip() in ("1", "true", "True")


def game_from_redis_to_model(raw_game: Dict[str, Any]) -> GameParams:
    from ..schemas.room import GameParams

    nominate_mode = str(raw_game.get("nominate_mode") or "players")
    if nominate_mode not in ("players", "head"):
        nominate_mode = "players"
    return GameParams(
        mode=(raw_game.get("mode") or "normal"),
        format=(raw_game.get("format") or "hosted"),
        spectators_limit=normalize_spectators_limit(raw_game.get("spectators_limit")),
        nominate_mode=nominate_mode,
        break_at_zero=raw_bool(raw_game.get("break_at_zero"), True),
        lift_at_zero=raw_bool(raw_game.get("lift_at_zero"), True),
        lift_3x=raw_bool(raw_game.get("lift_3x"), True),
        wink_knock=raw_bool(raw_game.get("wink_knock"), True),
        farewell_wills=raw_bool(raw_game.get("farewell_wills"), True),
        music=raw_bool(raw_game.get("music"), True),
    )


def parse_month_range(month_raw: str | None) -> tuple[datetime, datetime]:
    if not month_raw:
        today = date.today()
        year = today.year
        month = today.month
    else:
        try:
            year_s, month_s = month_raw.split("-", 1)
            year = int(year_s)
            month = int(month_s)
        except Exception:
            raise HTTPException(status_code=422, detail="invalid_month")

        if month < 1 or month > 12:
            raise HTTPException(status_code=422, detail="invalid_month")

    start = datetime(year, month, 1, tzinfo=timezone.utc)
    last_day = calendar.monthrange(year, month)[1]
    end = datetime(year, month, last_day, tzinfo=timezone.utc) + timedelta(days=1)
    return start, end


def parse_day_range(day: date) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return start, end


def site_settings_out(row) -> SiteSettingsOut:
    from ..schemas.admin import SiteSettingsOut

    return SiteSettingsOut(
        registration_enabled=bool(row.registration_enabled),
        rooms_can_create=bool(row.rooms_can_create),
        rooms_can_enter=bool(row.rooms_can_enter),
        games_can_start=bool(row.games_can_start),
        streams_can_start=bool(row.streams_can_start),
        chat_open_enabled=bool(getattr(row, "chat_open_enabled", True)),
        chat_messages_enabled=bool(getattr(row, "chat_messages_enabled", True)),
        verification_restrictions=bool(row.verification_restrictions),
        admin_banner_text=normalize_admin_banner_text(getattr(row, "admin_banner_text", "0")),
        admin_banner_link=normalize_admin_banner_link(getattr(row, "admin_banner_link", "0")),
        rooms_limit_global=int(row.rooms_limit_global),
        rooms_limit_per_user=int(row.rooms_limit_per_user),
        rooms_empty_ttl_seconds=int(row.rooms_empty_ttl_seconds),
        rooms_single_ttl_minutes=int(row.rooms_single_ttl_minutes),
        season_start_game_number=str(row.season_start_game_number),
        text_moderation_whitelist=normalize_text_moderation_whitelist(getattr(row, "text_moderation_whitelist", "0")),
        text_moderation_blacklist=normalize_text_moderation_blacklist(getattr(row, "text_moderation_blacklist", "0")),
    )


def game_settings_out(row) -> GameSettingsOut:
    from ..schemas.admin import GameSettingsOut

    return GameSettingsOut(
        game_min_ready_players=int(row.game_min_ready_players),
        role_pick_seconds=int(row.role_pick_seconds),
        mafia_talk_seconds=int(row.mafia_talk_seconds),
        player_talk_seconds=int(row.player_talk_seconds),
        player_talk_short_seconds=int(row.player_talk_short_seconds),
        player_foul_seconds=int(row.player_foul_seconds),
        night_action_seconds=int(row.night_action_seconds),
        vote_seconds=int(row.vote_seconds),
        winks_limit=int(row.winks_limit),
        knocks_limit=int(row.knocks_limit),
        wink_spot_chance_percent=int(row.wink_spot_chance_percent),
    )


def normalize_pagination(page: int, limit: int) -> tuple[int, int, int]:
    norm_limit = 100 if limit == 100 else 20
    norm_page = max(page, 1)
    offset = (norm_page - 1) * norm_limit
    return norm_limit, norm_page, offset


async def build_registrations_series(session: AsyncSession, start_dt: datetime, end_dt: datetime) -> list[RegistrationsPoint]:
    from ..schemas.admin import RegistrationsPoint

    rows = await session.execute(
        select(func.date_trunc("day", User.registered_at).label("day"), func.count(User.id))
        .where(
            User.registered_at >= start_dt,
            User.registered_at < end_dt,
            User.deleted_at.is_(None),
        )
        .group_by("day")
        .order_by("day")
    )
    reg_map: dict[str, int] = {}
    for day, cnt in rows.all():
        try:
            reg_map[day.date().isoformat()] = int(cnt or 0)
        except Exception:
            continue

    registrations: list[RegistrationsPoint] = []
    day_cursor = start_dt.date()
    end_date = (end_dt - timedelta(days=1)).date()
    while day_cursor <= end_date:
        key = day_cursor.isoformat()
        registrations.append(RegistrationsPoint(date=key, count=reg_map.get(key, 0)))
        day_cursor = day_cursor + timedelta(days=1)

    return registrations


async def build_registrations_monthly_series(session: AsyncSession) -> list[RegistrationsPoint]:
    from ..schemas.admin import RegistrationsPoint

    rows = await session.execute(
        select(func.date_trunc("month", User.registered_at).label("month"), func.count(User.id))
        .where(User.deleted_at.is_(None))
        .group_by("month")
        .order_by("month")
    )
    raw = rows.all()
    if not raw:
        return []

    reg_map: dict[str, int] = {}
    first_month = None
    for month_dt, cnt in raw:
        if not month_dt:
            continue

        key = f"{month_dt.year:04d}-{month_dt.month:02d}"
        reg_map[key] = int(cnt or 0)
        if first_month is None:
            first_month = month_dt

    if not first_month:
        return []

    start_year = first_month.year
    start_month = first_month.month
    now = datetime.now(timezone.utc)
    end_year = now.year
    end_month = now.month
    monthly: list[RegistrationsPoint] = []
    year = start_year
    month = start_month
    while (year, month) <= (end_year, end_month):
        key = f"{year:04d}-{month:02d}"
        monthly.append(RegistrationsPoint(date=key, count=reg_map.get(key, 0)))
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1

    return monthly


async def build_games_series(session: AsyncSession, start_dt: datetime, end_dt: datetime) -> list[RegistrationsPoint]:
    from ..schemas.admin import RegistrationsPoint

    rows = await session.execute(
        select(func.date_trunc("day", Game.finished_at).label("day"), func.count(Game.id))
        .where(Game.finished_at >= start_dt, Game.finished_at < end_dt)
        .group_by("day")
        .order_by("day")
    )
    games_map: dict[str, int] = {}
    for day, cnt in rows.all():
        try:
            games_map[day.date().isoformat()] = int(cnt or 0)
        except Exception:
            continue

    games: list[RegistrationsPoint] = []
    day_cursor = start_dt.date()
    end_date = (end_dt - timedelta(days=1)).date()
    while day_cursor <= end_date:
        key = day_cursor.isoformat()
        games.append(RegistrationsPoint(date=key, count=games_map.get(key, 0)))
        day_cursor = day_cursor + timedelta(days=1)

    return games


async def build_games_monthly_series(session: AsyncSession) -> list[RegistrationsPoint]:
    from ..schemas.admin import RegistrationsPoint

    rows = await session.execute(select(func.date_trunc("month", Game.finished_at).label("month"), func.count(Game.id)).group_by("month").order_by("month"))
    raw = rows.all()
    if not raw:
        return []

    games_map: dict[str, int] = {}
    first_month = None
    for month_dt, cnt in raw:
        if not month_dt:
            continue

        key = f"{month_dt.year:04d}-{month_dt.month:02d}"
        games_map[key] = int(cnt or 0)
        if first_month is None:
            first_month = month_dt

    if not first_month:
        return []

    start_year = first_month.year
    start_month = first_month.month
    now = datetime.now(timezone.utc)
    end_year = now.year
    end_month = now.month
    monthly: list[RegistrationsPoint] = []
    year = start_year
    month = start_month
    while (year, month) <= (end_year, end_month):
        key = f"{year:04d}-{month:02d}"
        monthly.append(RegistrationsPoint(date=key, count=games_map.get(key, 0)))
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1

    return monthly


def _collect_room_activity_user_ids(visitors_map: Any, spectators_map: Any) -> set[int]:
    user_ids: set[int] = set()
    for raw_map in (visitors_map, spectators_map):
        if not isinstance(raw_map, dict):
            continue
        for k in raw_map.keys():
            try:
                uid = int(k)
            except Exception:
                continue
            if uid > 0:
                user_ids.add(uid)

    return user_ids


async def _load_rooms_for_active_users_stats(session: AsyncSession, *, start_dt: datetime | None = None, end_dt: datetime | None = None) -> tuple[list[tuple[int, datetime, datetime | None, dict, dict]], dict[int, dict[str, Any]]]:
    room_q = select(Room.id, Room.created_at, Room.deleted_at, Room.visitors, Room.spectators_time)
    if start_dt is not None:
        room_q = room_q.where(Room.created_at >= start_dt)
    if end_dt is not None:
        room_q = room_q.where(Room.created_at < end_dt)
    room_q = room_q.order_by(Room.created_at, Room.id)

    rows = list((await session.execute(room_q)).all())
    if not rows:
        return [], {}

    live_room_ids = [int(rid) for rid, _created_at, deleted_at, _visitors, _spectators in rows if deleted_at is None]
    live_stats: dict[int, dict[str, Any]] = {}
    if live_room_ids:
        try:
            live_stats = await fetch_live_room_stats(get_redis(), live_room_ids)
        except Exception:
            log.warning("admin_stats.active_users.live_fetch_failed", rooms=len(live_room_ids))

    return rows, live_stats


async def build_active_users_series(session: AsyncSession, start_dt: datetime, end_dt: datetime) -> list[RegistrationsPoint]:
    from ..schemas.admin import RegistrationsPoint
    start_date = start_dt.date()
    end_date = (end_dt - timedelta(days=1)).date()
    if end_date < start_date:
        return []

    rows, live_stats = await _load_rooms_for_active_users_stats(session, start_dt=start_dt, end_dt=end_dt)
    users_map: dict[str, set[int]] = {}
    for rid, created_at, deleted_at, visitors, spectators_time in rows:
        key = created_at.date().isoformat()
        live = live_stats.get(int(rid)) if deleted_at is None else None
        visitors_map = live.get("visitors") if live else visitors
        spectators_map = live.get("spectators") if live else spectators_time
        bucket = users_map.setdefault(key, set())
        bucket.update(_collect_room_activity_user_ids(visitors_map, spectators_map))

    active_users: list[RegistrationsPoint] = []
    day_cursor = start_date
    while day_cursor <= end_date:
        key = day_cursor.isoformat()
        active_users.append(RegistrationsPoint(date=key, count=len(users_map.get(key, set()))))
        day_cursor = day_cursor + timedelta(days=1)

    return active_users


async def build_active_users_monthly_series(session: AsyncSession) -> list[RegistrationsPoint]:
    from ..schemas.admin import RegistrationsPoint
    rows, live_stats = await _load_rooms_for_active_users_stats(session)
    if not rows:
        return []

    users_map: dict[str, set[int]] = {}
    first_month = None
    for rid, created_at, deleted_at, visitors, spectators_time in rows:
        key = f"{created_at.year:04d}-{created_at.month:02d}"
        live = live_stats.get(int(rid)) if deleted_at is None else None
        visitors_map = live.get("visitors") if live else visitors
        spectators_map = live.get("spectators") if live else spectators_time
        bucket = users_map.setdefault(key, set())
        bucket.update(_collect_room_activity_user_ids(visitors_map, spectators_map))
        if first_month is None:
            first_month = created_at

    if not first_month:
        return []

    start_year = first_month.year
    start_month = first_month.month
    now = datetime.now(timezone.utc)
    end_year = now.year
    end_month = now.month
    monthly: list[RegistrationsPoint] = []
    year = start_year
    month = start_month
    while (year, month) <= (end_year, end_month):
        key = f"{year:04d}-{month:02d}"
        monthly.append(RegistrationsPoint(date=key, count=len(users_map.get(key, set()))))
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1

    return monthly


async def calc_total_stream_seconds(session: AsyncSession) -> int:
    total_stream_seconds = 0
    rows = await session.execute(select(Room.id, Room.deleted_at, Room.screen_time))
    room_rows = rows.all()
    active_room_ids = [int(rid) for rid, deleted_at, _screen_time in room_rows if deleted_at is None]
    live_stats: dict[int, dict[str, Any]] = {}
    if active_room_ids:
        try:
            live_stats = await fetch_live_room_stats(get_redis(), sorted(set(active_room_ids)))
        except Exception:
            log.warning("admin_stats.total_stream.live_fetch_failed", rooms=len(active_room_ids))

    for rid, deleted_at, screen_time in room_rows:
        live = live_stats.get(int(rid)) if deleted_at is None else None
        if live:
            try:
                total_stream_seconds += int(live.get("stream_seconds") or 0)
            except Exception:
                continue
        else:
            total_stream_seconds += sum_room_stream_seconds(screen_time)

    return total_stream_seconds


async def calc_room_stream_seconds_in_range(session: AsyncSession, start_dt: datetime, end_dt: datetime) -> int:
    if end_dt <= start_dt:
        return 0

    rows = await session.execute(
        select(Room.id, Room.created_at, Room.deleted_at, Room.screen_time).where(
            Room.created_at < end_dt,
            Room.created_at >= start_dt,
        )
    )
    room_rows = rows.all()
    if not room_rows:
        return 0

    active_room_ids = [int(rid) for rid, _created_at, deleted_at, _screen_time in room_rows if deleted_at is None]
    live_stats: dict[int, dict[str, Any]] = {}
    if active_room_ids:
        try:
            live_stats = await fetch_live_room_stats(get_redis(), sorted(set(active_room_ids)))
        except Exception:
            log.warning("admin_stats.period_stream.live_fetch_failed", rooms=len(active_room_ids))

    total_stream_seconds = 0
    for rid, _created_at, deleted_at, screen_time in room_rows:
        live = live_stats.get(int(rid)) if deleted_at is None else None
        if live:
            try:
                stream_seconds = max(0, int(live.get("stream_seconds") or 0))
            except Exception:
                stream_seconds = 0
        else:
            stream_seconds = max(0, sum_room_stream_seconds(screen_time))

        if stream_seconds <= 0:
            continue

        total_stream_seconds += stream_seconds

    return total_stream_seconds


def online_cutoff_ts(now_ts: int | None = None) -> int:
    ttl = settings.ONLINE_TTL_SECONDS
    if now_ts is None:
        now_ts = int(time())

    return int(now_ts) - ttl


def active_alive_game_room_key(user_id: int) -> str:
    return f"user:{int(user_id)}:active_alive_game_room"


def active_game_rooms_key(user_id: int) -> str:
    return f"user:{int(user_id)}:active_game_rooms"


def redis_text(raw: object, default: str = "") -> str:
    if raw is None:
        return default

    if isinstance(raw, bytes):
        return raw.decode("utf-8", "ignore")

    return str(raw)


def parse_cached_deleted_at(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))

    except Exception:
        return None


async def active_game_head_room_by_uid(r, user_ids: list[int]) -> dict[int, int]:
    user_id_set: set[int] = set()
    for raw_uid in user_ids:
        try:
            uid = int(raw_uid)
        except Exception:
            continue
        if uid > 0:
            user_id_set.add(uid)
    if not user_id_set:
        return {}

    try:
        raw_room_ids = await r.zrange("rooms:index", 0, -1)
    except Exception:
        return {}

    room_ids: list[int] = []
    for raw in raw_room_ids or []:
        try:
            rid = int(raw or 0)
        except Exception:
            continue
        if rid > 0:
            room_ids.append(rid)

    if not room_ids:
        return {}

    try:
        async with r.pipeline() as p:
            for rid in room_ids:
                await p.hget(f"room:{rid}:game_state", "phase")
                await p.hget(f"room:{rid}:game_state", "game_finished")
                await p.hget(f"room:{rid}:game_state", "head")
            rows = await p.execute()
    except Exception:
        return {}

    out: dict[int, int] = {}
    for idx, rid in enumerate(room_ids):
        base = idx * 3
        phase = redis_text(rows[base], "idle") if base < len(rows) else "idle"
        game_finished = redis_text(rows[base + 1], "0") if base + 1 < len(rows) else "0"
        try:
            head_uid = int(rows[base + 2] or 0) if base + 2 < len(rows) else 0
        except Exception:
            head_uid = 0

        if phase == "idle" or game_finished == "1" or head_uid not in user_id_set:
            continue
        out.setdefault(head_uid, rid)

    return out


def tg_room_invite_cooldown_key(user_id: int) -> str:
    return f"user:{int(user_id)}:tg_room_invite_cooldown"


def _normalize_active_game_room_ids(values: Iterable[object]) -> set[int]:
    out: set[int] = set()
    for raw in values:
        try:
            room_id = int(raw or 0)
        except Exception:
            continue
        if room_id > 0:
            out.add(room_id)
    return out


async def _filter_user_active_game_rooms(r, user_id: int, room_ids: Iterable[int]) -> set[int]:
    uid = int(user_id)
    ids = sorted(_normalize_active_game_room_ids(room_ids))
    if uid <= 0 or not ids:
        return set()

    async with r.pipeline() as p:
        for rid in ids:
            await p.hget(f"room:{rid}:game_state", "phase")
            await p.hget(f"room:{rid}:game_state", "game_finished")
            await p.sismember(f"room:{rid}:game_players", str(uid))
        rows = await p.execute()

    out: set[int] = set()
    for idx, rid in enumerate(ids):
        base = idx * 3
        phase = str(rows[base] or "idle") if base < len(rows) else "idle"
        game_finished = str(rows[base + 1] or "0") if base + 1 < len(rows) else "0"
        is_player = bool(rows[base + 2]) if base + 2 < len(rows) else False
        if phase != "idle" and game_finished != "1" and is_player:
            out.add(rid)

    return out


async def _scan_user_active_game_rooms(r, user_id: int) -> set[int]:
    uid = int(user_id)
    if uid <= 0:
        return set()

    raw_room_ids = await r.zrange("rooms:index", 0, -1)
    candidate_ids = _normalize_active_game_room_ids(raw_room_ids or [])
    return await _filter_user_active_game_rooms(r, uid, candidate_ids)


async def get_active_alive_game_room(user_id: int, *, redis_client=None, strict: bool = False) -> int | None:
    r = redis_client or get_redis()
    try:
        raw = await r.get(active_alive_game_room_key(user_id))
    except Exception as exc:
        if strict:
            raise RuntimeError("active_alive_game_room_unavailable") from exc

        return None

    try:
        room_id = int(raw or 0)
    except Exception:
        return None

    return room_id if room_id > 0 else None


async def is_user_in_active_alive_game(user_id: int, *, redis_client=None, strict: bool = False) -> bool:
    return (await get_active_alive_game_room(user_id, redis_client=redis_client, strict=strict)) is not None


async def get_active_game_rooms(user_id: int, *, redis_client=None, strict: bool = False, scan_if_missing: bool = False) -> set[int]:
    r = redis_client or get_redis()
    try:
        uid = int(user_id)
    except Exception:
        return set()

    if uid <= 0:
        return set()

    try:
        async with r.pipeline() as p:
            await p.smembers(active_game_rooms_key(uid))
            await p.get(active_alive_game_room_key(uid))
            raw_rooms, raw_legacy_room = await p.execute()

        candidates = _normalize_active_game_room_ids(raw_rooms or [])
        candidates.update(_normalize_active_game_room_ids([raw_legacy_room]))
        active_rooms = await _filter_user_active_game_rooms(r, uid, candidates)
        if not active_rooms and scan_if_missing:
            active_rooms = await _scan_user_active_game_rooms(r, uid)
        return active_rooms

    except Exception as exc:
        if strict:
            raise RuntimeError("active_game_rooms_unavailable") from exc

        return set()


async def is_user_in_active_game(user_id: int, *, redis_client=None, strict: bool = False, scan_if_missing: bool = False) -> bool:
    return bool(await get_active_game_rooms(user_id, redis_client=redis_client, strict=strict, scan_if_missing=scan_if_missing))


async def prune_online_users(r, cutoff_ts: int) -> None:
    await r.zremrangebyscore("online:users:seen", "-inf", int(cutoff_ts) - 1)


async def fetch_active_rooms_stats(r) -> int:
    rids = await r.zrange("rooms:index", 0, -1)
    active_room_users = 0
    if rids:
        async with r.pipeline() as p:
            for rid in rids:
                await p.scard(f"room:{int(rid)}:members")
                await p.scard(f"room:{int(rid)}:spectators")
            counts = await p.execute()
        for idx in range(0, len(counts), 2):
            try:
                members_count = int(counts[idx] or 0)
            except Exception:
                members_count = 0
            try:
                spectators_count = int(counts[idx + 1] or 0)
            except Exception:
                spectators_count = 0

            total_users = members_count + spectators_count
            if total_users > 0:
                active_room_users += total_users

    return active_room_users


async def fetch_online_user_ids(r) -> list[int]:
    cutoff = online_cutoff_ts()
    await prune_online_users(r, cutoff)
    raw_ids = await r.zrangebyscore("online:users:seen", cutoff, "+inf")
    ids: list[int] = []
    for item in raw_ids or []:
        try:
            uid = int(item)
        except Exception:
            continue
        if uid > 0:
            ids.append(uid)

    return ids


async def fetch_effective_online_user_ids(r, user_ids: Iterable[int], *, base_online_ids: set[int] | None = None) -> set[int]:
    ids: set[int] = set()
    for item in user_ids:
        try:
            uid = int(item)
        except Exception:
            continue
        if uid > 0:
            ids.add(uid)
    if not ids:
        return set()

    if base_online_ids is None:
        base_online_ids = set(await fetch_online_user_ids(r))
    online_ids = {uid for uid in base_online_ids if uid in ids}
    pending_ids = [uid for uid in ids if uid not in online_ids]
    if not pending_ids:
        return online_ids

    try:
        async with r.pipeline() as p:
            for uid in pending_ids:
                await p.get(f"user:{uid}:room")
            raw_rooms = await p.execute()
    except Exception:
        return online_ids

    checks: list[tuple[int, int]] = []
    for uid, raw in zip(pending_ids, raw_rooms):
        try:
            rid = int(raw or 0)
        except Exception:
            rid = 0
        if rid > 0:
            checks.append((uid, rid))
    if not checks:
        return online_ids

    try:
        async with r.pipeline() as p:
            for uid, rid in checks:
                await p.sismember(f"room:{rid}:members", str(uid))
                await p.sismember(f"room:{rid}:spectators", str(uid))
            presence = await p.execute()
    except Exception:
        return online_ids

    for idx, (uid, _) in enumerate(checks):
        is_member = bool(presence[idx * 2]) if idx * 2 < len(presence) else False
        is_spectator = bool(presence[idx * 2 + 1]) if idx * 2 + 1 < len(presence) else False
        if is_member or is_spectator:
            online_ids.add(uid)

    return online_ids


def pair(uid: int, other: int) -> tuple[int, int]:
    return (uid, other) if uid < other else (other, uid)


async def load_link(db: AsyncSession, uid: int, other: int) -> FriendLink | None:
    return await db.scalar(
        select(FriendLink).where(
            or_(
                and_(FriendLink.requester_id == uid, FriendLink.addressee_id == other),
                and_(FriendLink.requester_id == other, FriendLink.addressee_id == uid),
            )
        ).limit(1)
    )


async def friend_status_for(db: AsyncSession, viewer_id: int, target_id: int) -> str:
    if target_id == viewer_id:
        return "self"

    link = await load_link(db, viewer_id, target_id)
    if not link:
        return "none"

    if link.status == "accepted":
        return "friends"

    if int(link.requester_id) == viewer_id:
        return "outgoing"

    return "incoming"


async def raise_missing_incoming_request_error(db: AsyncSession, uid: int, requester_id: int) -> None:
    existing = await load_link(db, uid, requester_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="request_revoked")

    if existing.status == "accepted":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_friends")

    if existing.status == "pending" and int(existing.requester_id) == uid:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="outgoing_request")

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="request_revoked")


async def raise_missing_outgoing_request_error(db: AsyncSession, uid: int, target_id: int) -> None:
    existing = await load_link(db, uid, target_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="request_not_found")

    if existing.status == "accepted":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_friends")

    if existing.status == "pending" and int(existing.requester_id) != uid:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="incoming_request")

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="request_not_found")


async def emit_notify(user_id: int, note: Notif, *, kind: str, no_toast: bool = False, extra: dict | None = None) -> None:
    payload = {
        "id": note.id,
        "title": note.title,
        "text": note.text,
        "date": note.created_at.isoformat(),
        "kind": kind,
        "ttl_ms": 15000,
        "read": note.read_at is not None,
    }
    if no_toast:
        payload["no_toast"] = True
    if extra:
        payload.update(extra)
    with suppress(Exception):
        await sio.emit("notify", payload, room=f"user:{int(user_id)}", namespace="/auth")


async def emit_friends_update(user_id: int, other_id: int, status: str) -> None:
    payload = {"user_id": int(other_id), "status": status}
    with suppress(Exception):
        await sio.emit("friends_update", payload, room=f"user:{int(user_id)}", namespace="/auth")


async def emit_friends_profile_sync(user_id: int, target_user_id: int, *, role: str | None = None) -> None:
    uid = int(user_id)
    target_uid = int(target_user_id)
    if uid <= 0 or target_uid <= 0:
        return

    payload = {
        "user_id": target_uid,
        "role": normalize_user_role(role),
    }
    with suppress(Exception):
        await sio.emit("friends_profile_sync", payload, room=f"user:{uid}", namespace="/auth")


async def emit_role_change_friend_profile_syncs(session: AsyncSession, user_id: int, *, role: str | None = None) -> None:
    uid = int(user_id)
    if uid <= 0:
        return

    rows = await session.execute(
        select(FriendLink.requester_id, FriendLink.addressee_id).where(
            or_(FriendLink.requester_id == uid, FriendLink.addressee_id == uid)
        )
    )
    recipient_ids: set[int] = set()
    for requester_id, addressee_id in rows.all():
        try:
            requester_uid = int(requester_id)
            addressee_uid = int(addressee_id)
        except Exception:
            continue
        other_uid = addressee_uid if requester_uid == uid else requester_uid
        if other_uid > 0:
            recipient_ids.add(other_uid)

    normalized_role = normalize_user_role(role)
    for recipient_uid in sorted(recipient_ids):
        await emit_friends_profile_sync(recipient_uid, uid, role=normalized_role)


async def emit_room_role_sync(user_id: int, *, role: str | None = None) -> None:
    uid = int(user_id)
    if uid <= 0:
        return

    normalized_base_role = normalize_user_role(role)
    r = get_redis()
    room_updates: dict[int, dict[str, str]] = {}

    def remember_room_update(rid: int, current_role: str | None) -> None:
        if rid <= 0:
            return

        current_role_value = str(current_role or "").strip().lower()
        next_role = "host" if current_role_value == "host" else normalized_base_role
        room_updates[rid] = {
            "role": next_role,
            "base_role": normalized_base_role,
            "moderation_role": room_moderation_role(next_role, normalized_base_role),
        }

    try:
        participants = tuple(sio.manager.get_participants("/room", f"user:{uid}"))
    except Exception:
        participants = ()

    for sid, _ in participants:
        try:
            sess = await sio.get_session(sid, namespace="/room")
        except Exception:
            continue
        if not sess:
            continue

        try:
            rid = int(sess.get("rid") or 0)
        except Exception:
            rid = 0

        current_role = str(sess.get("role") or "").strip().lower()
        if not current_role and rid > 0:
            try:
                current_role = str(await r.hget(f"room:{rid}:user:{uid}:info", "role") or "").strip().lower()
            except Exception:
                current_role = ""

        next_role = "host" if current_role == "host" else normalized_base_role
        next_session = dict(sess)
        next_session["role"] = next_role
        next_session["base_role"] = normalized_base_role
        try:
            await sio.save_session(sid, next_session, namespace="/room")
        except Exception:
            pass

        remember_room_update(rid, current_role)

    try:
        raw_current_room_id = await r.get(f"user:{uid}:room")
    except Exception:
        raw_current_room_id = None

    try:
        current_room_id = int(raw_current_room_id or 0)
    except Exception:
        current_room_id = 0

    if current_room_id > 0 and current_room_id not in room_updates:
        try:
            current_role = str(await r.hget(f"room:{current_room_id}:user:{uid}:info", "role") or "").strip().lower()
        except Exception:
            current_role = ""
        if current_role:
            remember_room_update(current_room_id, current_role)

    for rid, payload in room_updates.items():
        try:
            await r.hset(
                f"room:{rid}:user:{uid}:info",
                mapping={
                    "role": payload["role"],
                    "base_role": payload["base_role"],
                },
            )
        except Exception as exc:
            log.warning("room.role_sync.cache_failed", rid=rid, uid=uid, err=type(exc).__name__)

        with suppress(Exception):
            await sio.emit(
                "role_sync",
                {
                    "user_id": uid,
                    "role": payload["role"],
                    "base_role": payload["base_role"],
                    "moderation_role": payload["moderation_role"],
                },
                room=f"room:{rid}",
                namespace="/room",
            )


async def fetch_user_avatar_map(session: AsyncSession, user_ids: set[int]) -> dict[int, str | None]:
    avatar_map: dict[int, str | None] = {}
    if not user_ids:
        return avatar_map

    profiles = await get_user_profiles_cached(session, user_ids)
    for uid, profile in profiles.items():
        avatar_map[int(uid)] = profile.get("avatar_name")

    return avatar_map


async def fetch_user_name_avatar_maps(session: AsyncSession, user_ids: set[int]) -> tuple[dict[int, str | None], dict[int, str | None]]:
    name_map: dict[int, str | None] = {}
    avatar_map: dict[int, str | None] = {}
    if not user_ids:
        return name_map, avatar_map

    profiles = await get_user_profiles_cached(session, user_ids)
    for uid, profile in profiles.items():
        name_map[int(uid)] = profile.get("username")
        avatar_map[int(uid)] = profile.get("avatar_name")

    return name_map, avatar_map


def collect_room_user_ids(rooms: Sequence[Room]) -> set[int]:
    user_ids: set[int] = set()
    for room in rooms:
        try:
            user_ids.add(int(room.creator))
        except Exception:
            pass
        if isinstance(room.visitors, dict):
            for k in room.visitors.keys():
                try:
                    user_ids.add(int(k))
                except Exception:
                    continue
        if isinstance(room.spectators_time, dict):
            for k in room.spectators_time.keys():
                try:
                    user_ids.add(int(k))
                except Exception:
                    continue
        if isinstance(room.screen_time, dict):
            for k in room.screen_time.keys():
                try:
                    user_ids.add(int(k))
                except Exception:
                    continue

    return user_ids


def parse_room_game_params(game: dict | None) -> dict[str, Any]:
    game = game or {}
    game_mode = str(game.get("mode") or "normal")
    game_format = str(game.get("format") or "hosted")
    nominate_mode = str(game.get("nominate_mode") or "players")
    if nominate_mode not in ("players", "head"):
        nominate_mode = "players"
    spectators_limit = normalize_spectators_limit(game.get("spectators_limit"))

    return {
        "mode": game_mode,
        "format": game_format,
        "spectators_limit": spectators_limit,
        "nominate_mode": nominate_mode,
        "break_at_zero": raw_bool(game.get("break_at_zero"), True),
        "lift_at_zero": raw_bool(game.get("lift_at_zero"), True),
        "lift_3x": raw_bool(game.get("lift_3x"), True),
        "wink_knock": raw_bool(game.get("wink_knock"), True),
        "farewell_wills": raw_bool(game.get("farewell_wills"), True),
        "music": raw_bool(game.get("music"), True),
    }


def build_room_user_stats(raw_map: dict | None, name_map: dict[int, str | None], avatar_map: dict[int, str | None]) -> list[AdminRoomUserStat]:
    from ..schemas.admin import AdminRoomUserStat

    items: list[AdminRoomUserStat] = []
    if isinstance(raw_map, dict):
        for k, v in raw_map.items():
            try:
                uid = int(k)
            except Exception:
                continue
            try:
                minutes = int(v or 0) // 60
            except Exception:
                minutes = 0
            items.append(
                AdminRoomUserStat(
                    id=uid,
                    username=name_map.get(uid),
                    avatar_name=avatar_map.get(uid),
                    minutes=minutes,
                )
            )
    items.sort(key=lambda item: item.minutes, reverse=True)

    return items


def sum_room_stream_seconds(screen_time: dict | None) -> int:
    total = 0
    if isinstance(screen_time, dict):
        for v in screen_time.values():
            try:
                total += int(v or 0)
            except Exception:
                continue

    return total


def _map_seconds(raw: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        try:
            out[str(k)] = int(v)
        except Exception:
            continue
    return out


async def fetch_live_room_stats(r, room_ids: list[int]) -> dict[int, dict[str, Any]]:
    if not room_ids:
        return {}

    params_fields = (
        "title",
        "user_limit",
        "creator",
        "creator_name",
        "creator_avatar_name",
        "created_at",
        "privacy",
        "anonymity",
    )
    now_ts = int(time())
    async with r.pipeline() as p:
        for rid in room_ids:
            await p.hgetall(f"room:{rid}:visitors")
            await p.smembers(f"room:{rid}:members")
            await p.hgetall(f"room:{rid}:spectators_time")
            await p.hgetall(f"room:{rid}:spectators_join")
            await p.hgetall(f"room:{rid}:screen_time")
            await p.get(f"room:{rid}:screen_owner")
            await p.get(f"room:{rid}:screen_started_at")
            await p.hmget(f"room:{rid}:params", *params_fields)
            await p.hgetall(f"room:{rid}:game")
        raw = await p.execute()

    room_chunks: dict[int, dict[str, Any]] = {}
    join_reqs: list[tuple[int, str]] = []
    step = 9
    for idx, rid in enumerate(room_ids):
        base = idx * step
        visitors_raw = raw[base]
        members_raw = raw[base + 1]
        spectators_raw = raw[base + 2]
        spectators_join_raw = raw[base + 3]
        screen_raw = raw[base + 4]
        screen_owner_raw = raw[base + 5]
        screen_started_raw = raw[base + 6]
        params_vals = raw[base + 7] or []
        game_raw = raw[base + 8] or {}

        title_raw = params_vals[0] if len(params_vals) > 0 else None
        user_limit_raw = params_vals[1] if len(params_vals) > 1 else None
        creator_raw = params_vals[2] if len(params_vals) > 2 else None
        creator_name_raw = params_vals[3] if len(params_vals) > 3 else None
        creator_avatar_name_raw = params_vals[4] if len(params_vals) > 4 else None
        created_at_raw = params_vals[5] if len(params_vals) > 5 else None
        privacy_raw = params_vals[6] if len(params_vals) > 6 else None
        anonymity_raw = params_vals[7] if len(params_vals) > 7 else None

        members = set(members_raw or [])
        for uid in members:
            join_reqs.append((rid, str(uid)))

        game_payload: dict[str, Any] | None = None
        if isinstance(game_raw, dict) and game_raw:
            try:
                model = game_from_redis_to_model(game_raw)
                game_payload = {
                    "mode": model.mode,
                    "format": model.format,
                    "spectators_limit": model.spectators_limit,
                    "nominate_mode": model.nominate_mode,
                    "break_at_zero": model.break_at_zero,
                    "lift_at_zero": model.lift_at_zero,
                    "lift_3x": model.lift_3x,
                    "wink_knock": model.wink_knock,
                    "farewell_wills": model.farewell_wills,
                    "music": model.music,
                }
            except Exception:
                game_payload = None

        room_chunks[rid] = {
            "visitors": _map_seconds(visitors_raw),
            "members": members,
            "spectators": _map_seconds(spectators_raw),
            "spectators_join": _map_seconds(spectators_join_raw),
            "streams": _map_seconds(screen_raw),
            "screen_owner": _parse_int(screen_owner_raw),
            "screen_started_at": _parse_int(screen_started_raw),
            "title": str(title_raw) if title_raw is not None else None,
            "user_limit": _parse_int(user_limit_raw),
            "creator": _parse_int(creator_raw),
            "creator_name": str(creator_name_raw) if creator_name_raw is not None else None,
            "creator_avatar_name": str(creator_avatar_name_raw) if creator_avatar_name_raw else None,
            "created_at": str(created_at_raw) if created_at_raw is not None else None,
            "privacy": str(privacy_raw or "open"),
            "anonymity": "hidden" if str(anonymity_raw or "visible") == "hidden" else "visible",
            "game": game_payload,
        }

    if join_reqs:
        async with r.pipeline() as p:
            for rid, uid in join_reqs:
                await p.hget(f"room:{rid}:user:{uid}:info", "join_date")
            join_vals = await p.execute()
        for i, (rid, uid) in enumerate(join_reqs):
            join_ts = _parse_int(join_vals[i])
            visitors_map: dict[str, int] = room_chunks[rid]["visitors"]
            if join_ts > 0:
                dt = now_ts - join_ts
                if dt > 0:
                    visitors_map[uid] = visitors_map.get(uid, 0) + dt
                else:
                    visitors_map.setdefault(uid, 0)
            else:
                visitors_map.setdefault(uid, 0)

    out: dict[int, dict[str, Any]] = {}
    for rid, chunk in room_chunks.items():
        spectators_map: dict[str, int] = chunk["spectators"]
        for uid, join_ts in chunk["spectators_join"].items():
            if join_ts > 0:
                dt = now_ts - int(join_ts)
                if dt > 0:
                    spectators_map[uid] = spectators_map.get(uid, 0) + dt
                else:
                    spectators_map.setdefault(uid, 0)
            else:
                spectators_map.setdefault(uid, 0)

        stream_map: dict[str, int] = chunk["streams"]
        screen_owner = int(chunk["screen_owner"])
        screen_started_at = int(chunk["screen_started_at"])
        if screen_owner > 0:
            owner_key = str(screen_owner)
            if screen_started_at > 0:
                dt = now_ts - screen_started_at
                if dt > 0:
                    stream_map[owner_key] = stream_map.get(owner_key, 0) + dt
                else:
                    stream_map.setdefault(owner_key, 0)
            else:
                stream_map.setdefault(owner_key, 0)

        stream_seconds = sum(int(v or 0) for v in stream_map.values())
        out[rid] = {
            "visitors": chunk["visitors"],
            "spectators": spectators_map,
            "streams": stream_map,
            "visitors_count": len(chunk["visitors"]),
            "spectators_count": len(spectators_map),
            "stream_seconds": stream_seconds,
            "has_stream": bool(stream_map) or screen_owner > 0,
            "title": chunk["title"],
            "user_limit": chunk["user_limit"],
            "creator": chunk["creator"],
            "creator_name": chunk["creator_name"],
            "creator_avatar_name": chunk["creator_avatar_name"],
            "created_at": chunk["created_at"],
            "privacy": chunk["privacy"],
            "anonymity": chunk["anonymity"],
            "game": chunk["game"],
        }

    return out


async def aggregate_user_room_stats(session: AsyncSession, ids: list[int]) -> tuple[dict[int, int], dict[int, int], dict[int, int], dict[int, int], dict[int, int], dict[int, int]]:
    rooms_created, room_seconds, stream_seconds, spectator_seconds = await aggregate_user_room_time_stats(session, ids)
    games_played: dict[int, int] = {uid: 0 for uid in ids}
    games_hosted: dict[int, int] = {uid: 0 for uid in ids}

    if not ids:
        return rooms_created, room_seconds, stream_seconds, spectator_seconds, games_played, games_hosted

    id_strs = [str(i) for i in ids]
    scan_all = len(ids) > 200
    id_set = set(ids)

    if scan_all:
        rows = await session.execute(select(Game.roles))
        for roles_map in rows.scalars().all():
            if not isinstance(roles_map, dict):
                continue
            for k in roles_map.keys():
                try:
                    uid = int(k)
                except Exception:
                    continue
                if uid in id_set:
                    games_played[uid] += 1
    else:
        role_filters = [Game.roles.has_key(i) for i in id_strs]
        rows = await session.execute(select(Game.roles).where(or_(*role_filters)))
        for roles_map in rows.scalars().all():
            if not isinstance(roles_map, dict):
                continue
            for k in roles_map.keys():
                try:
                    uid = int(k)
                except Exception:
                    continue
                if uid in id_set:
                    games_played[uid] += 1

    host_rows = await session.execute(select(Game.head_id, func.count(Game.id)).where(Game.head_id.in_(ids)).group_by(Game.head_id))
    for head_id, cnt in host_rows.all():
        try:
            hid = int(head_id)
        except Exception:
            continue
        if hid in games_hosted:
            try:
                games_hosted[hid] = int(cnt or 0)
            except Exception:
                continue

    return rooms_created, room_seconds, stream_seconds, spectator_seconds, games_played, games_hosted


async def _fetch_users_last_room_activity_id(session: AsyncSession, ids: list[int], *, room_column: Any, live_key: str, log_event: str) -> dict[int, int | None]:
    out: dict[int, int | None] = {uid: None for uid in ids}
    if not ids:
        return out

    id_set = set(ids)
    pending = set(ids)
    id_strs = [str(i) for i in ids]
    scan_all = len(ids) > 200

    if scan_all:
        room_q = select(Room.id, Room.deleted_at, room_column)
    else:
        room_filters = [room_column.has_key(i) for i in id_strs]
        room_filters.append(Room.deleted_at.is_(None))
        room_q = select(Room.id, Room.deleted_at, room_column).where(or_(*room_filters))
    room_rows = (await session.execute(room_q.order_by(Room.id.desc()))).all()

    active_room_ids = [int(rid) for rid, deleted_at, _room_activity in room_rows if deleted_at is None]
    live_stats: dict[int, dict[str, Any]] = {}
    if active_room_ids:
        try:
            live_stats = await fetch_live_room_stats(get_redis(), sorted(set(active_room_ids)))
        except Exception:
            log.warning(log_event, rooms=len(active_room_ids))

    for rid, deleted_at, room_activity in room_rows:
        if not pending:
            break
        room_id = int(rid)
        live = live_stats.get(room_id) if deleted_at is None else None
        activity_map = live.get(live_key) if live else room_activity
        if not isinstance(activity_map, dict):
            continue
        for raw_uid in activity_map.keys():
            try:
                uid = int(raw_uid)
            except Exception:
                continue
            if uid not in id_set or uid not in pending:
                continue
            out[uid] = room_id
            pending.remove(uid)

    return out


async def fetch_users_last_room_id(session: AsyncSession, ids: list[int]) -> dict[int, int | None]:
    return await _fetch_users_last_room_activity_id(
        session,
        ids,
        room_column=Room.visitors,
        live_key="visitors",
        log_event="users_last_room.live_fetch_failed",
    )


async def fetch_users_last_spectator_room_id(session: AsyncSession, ids: list[int]) -> dict[int, int | None]:
    return await _fetch_users_last_room_activity_id(
        session,
        ids,
        room_column=Room.spectators_time,
        live_key="spectators",
        log_event="users_last_spectator_room.live_fetch_failed",
    )


def _season_game_id_bounds_or_raise(season: int | None) -> tuple[int | None, int | None]:
    if season is None:
        return None, None

    try:
        season_no = int(season)
    except Exception as exc:
        raise ValueError("season_invalid") from exc
    if season_no < 1:
        raise ValueError("season_invalid")

    from ..security.parameters import get_cached_settings

    starts = tuple(int(v) for v in get_cached_settings().season_start_game_numbers if int(v) > 0)
    if not starts:
        starts = (1,)
    if season_no > len(starts):
        raise ValueError("season_not_found")

    start_id = int(starts[season_no - 1])
    end_id: int | None = int(starts[season_no] - 1) if season_no < len(starts) else None
    return start_id, end_id


async def aggregate_user_games_in_owned_rooms_stats(session: AsyncSession, ids: list[int], season: int | None = None) -> dict[int, int]:
    games_in_owned_rooms: dict[int, int] = {uid: 0 for uid in ids}
    if not ids:
        return games_in_owned_rooms

    start_id, end_id = _season_game_id_bounds_or_raise(season)

    games_q = select(Game.room_owner_id, func.count(Game.id)).where(Game.room_owner_id.in_(ids))
    if start_id is not None:
        games_q = games_q.where(Game.id >= start_id)
    if end_id is not None and end_id > 0:
        games_q = games_q.where(Game.id <= end_id)
    games_q = games_q.group_by(Game.room_owner_id)
    rows = await session.execute(games_q)
    for owner_id, cnt in rows.all():
        try:
            uid = int(owner_id)
            games_in_owned_rooms[uid] = max(0, int(cnt or 0))
        except Exception:
            continue

    return games_in_owned_rooms


async def fetch_users_last_game_at(session: AsyncSession, ids: list[int]) -> dict[int, datetime | None]:
    out: dict[int, datetime | None] = {uid: None for uid in ids}
    if not ids:
        return out

    id_set = set(ids)
    pending = set(ids)
    id_strs = [str(i) for i in ids]
    scan_all = len(ids) > 200

    if scan_all:
        rows = await session.execute(select(Game.roles, Game.finished_at).order_by(Game.finished_at.desc(), Game.id.desc()))
    else:
        role_filters = [Game.roles.has_key(i) for i in id_strs]
        rows = await session.execute(
            select(Game.roles, Game.finished_at)
            .where(or_(*role_filters))
            .order_by(Game.finished_at.desc(), Game.id.desc())
        )

    for roles_map, finished_at in rows.all():
        if not pending:
            break
        if not isinstance(roles_map, dict):
            continue
        if finished_at is None:
            continue
        for raw_uid in roles_map.keys():
            try:
                uid = int(raw_uid)
            except Exception:
                continue
            if uid not in id_set or uid not in pending:
                continue
            out[uid] = finished_at
            pending.remove(uid)

    return out


async def aggregate_user_room_time_stats(session: AsyncSession, ids: list[int], season: int | None = None) -> tuple[dict[int, int], dict[int, int], dict[int, int], dict[int, int]]:
    rooms_created: dict[int, int] = {uid: 0 for uid in ids}
    room_seconds: dict[int, int] = {uid: 0 for uid in ids}
    stream_seconds: dict[int, int] = {uid: 0 for uid in ids}
    spectator_seconds: dict[int, int] = {uid: 0 for uid in ids}

    if not ids:
        return rooms_created, room_seconds, stream_seconds, spectator_seconds

    season_scope = None
    include_active_rooms = season is None
    if season is not None:
        try:
            season_no = int(season)
        except Exception as exc:
            raise ValueError("season_invalid") from exc
        if season_no < 1:
            raise ValueError("season_invalid")

        from ..security.parameters import get_cached_settings

        starts = tuple(int(v) for v in get_cached_settings().season_start_game_numbers if int(v) > 0)
        if not starts:
            starts = (1,)
        if season_no > len(starts):
            raise ValueError("season_not_found")

        start_id = int(starts[season_no - 1])
        end_id: int | None = int(starts[season_no] - 1) if season_no < len(starts) else None

        game_time_q = select(func.min(Game.started_at), func.max(Game.finished_at)).where(Game.id >= start_id)
        if end_id is not None and end_id > 0:
            game_time_q = game_time_q.where(Game.id <= end_id)
        game_time_row = await session.execute(game_time_q)
        season_start_dt, season_end_dt = game_time_row.one()

        current_season = len(starts)
        include_active_rooms = season_no == current_season
        if season_start_dt is None:
            return rooms_created, room_seconds, stream_seconds, spectator_seconds

        season_scope_parts = [Room.created_at >= season_start_dt]
        if season_no != current_season:
            if season_end_dt is None:
                return rooms_created, room_seconds, stream_seconds, spectator_seconds
            season_scope_parts.append(Room.created_at <= season_end_dt)
        season_scope = and_(*season_scope_parts)

    counts_q = select(Room.creator, func.count(Room.id)).where(Room.creator.in_(ids))
    if season_scope is not None:
        counts_q = counts_q.where(season_scope)
    counts_q = counts_q.group_by(Room.creator)
    counts = await session.execute(counts_q)
    for creator, cnt in counts.all():
        try:
            rooms_created[int(creator)] = int(cnt or 0)
        except Exception:
            continue

    id_strs = [str(i) for i in ids]
    scan_all = len(ids) > 200
    if scan_all:
        room_q = select(Room.id, Room.deleted_at, Room.visitors, Room.screen_time, Room.spectators_time)
        if season_scope is not None:
            room_q = room_q.where(season_scope)
        room_rows = (await session.execute(room_q)).all()
    else:
        room_filters = [Room.creator.in_(ids)]
        room_filters += [Room.visitors.has_key(i) for i in id_strs]
        room_filters += [Room.screen_time.has_key(i) for i in id_strs]
        room_filters += [Room.spectators_time.has_key(i) for i in id_strs]
        if include_active_rooms:
            room_filters.append(Room.deleted_at.is_(None))
        room_q = select(Room.id, Room.deleted_at, Room.visitors, Room.screen_time, Room.spectators_time).where(or_(*room_filters))
        if season_scope is not None:
            room_q = room_q.where(season_scope)
        room_rows = (await session.execute(room_q)).all()

    live_stats: dict[int, dict[str, Any]] = {}
    active_room_ids = [int(rid) for rid, deleted_at, _vis, _scr, _spec in room_rows if deleted_at is None]
    if active_room_ids:
        try:
            live_stats = await fetch_live_room_stats(get_redis(), sorted(set(active_room_ids)))
        except Exception:
            log.warning("user_room_stats.live_fetch_failed", rooms=len(active_room_ids))

    id_set = set(ids)
    for rid, deleted_at, visitors, screen_time, spectators_time in room_rows:
        live = live_stats.get(int(rid)) if deleted_at is None else None
        visitors_map = live.get("visitors") if live else visitors
        screen_map = live.get("streams") if live else screen_time
        spectators_map = live.get("spectators") if live else spectators_time

        if isinstance(visitors_map, dict):
            for k, v in visitors_map.items():
                try:
                    uid = int(k)
                except Exception:
                    continue
                if uid in id_set:
                    try:
                        room_seconds[uid] += int(v or 0)
                    except Exception:
                        continue

        if isinstance(screen_map, dict):
            for k, v in screen_map.items():
                try:
                    uid = int(k)
                except Exception:
                    continue
                if uid in id_set:
                    try:
                        stream_seconds[uid] += int(v or 0)
                    except Exception:
                        continue

        if isinstance(spectators_map, dict):
            for k, v in spectators_map.items():
                try:
                    uid = int(k)
                except Exception:
                    continue
                if uid in id_set:
                    try:
                        spectator_seconds[uid] += int(v or 0)
                    except Exception:
                        continue

    return rooms_created, room_seconds, stream_seconds, spectator_seconds


async def build_user_stats_out(db: AsyncSession, uid: int, season: int | None = None) -> UserStatsOut:
    from ..schemas.user import UserStatsOut, UserTopPlayerOut
    from ..services.user_stats import get_user_game_stats_cached

    try:
        rooms_created, room_seconds, stream_seconds, spectator_seconds = await aggregate_user_room_time_stats(db, [uid], season=season)
        games_in_owned_rooms = await aggregate_user_games_in_owned_rooms_stats(db, [uid], season=season)
        room_minutes = max(0, int(room_seconds.get(uid, 0)) // 60)
        stream_minutes = max(0, int(stream_seconds.get(uid, 0)) // 60)
        spectator_minutes = max(0, int(spectator_seconds.get(uid, 0)) // 60)
        game_stats = await get_user_game_stats_cached(db, uid, season)
    except ValueError as exc:
        detail = str(exc) or "season_invalid"
        if detail not in {"season_invalid", "season_not_found"}:
            detail = "season_invalid"
        raise HTTPException(status_code=422, detail=detail)

    top_player_ids = {int(item.id) for item in (game_stats.top_players or []) if int(item.id) > 0}
    if top_player_ids:
        profiles = await get_user_profiles_cached(db, top_player_ids)
        refreshed_top_players: list[UserTopPlayerOut] = []
        for item in game_stats.top_players:
            profile = profiles.get(int(item.id)) or {}
            username_raw = profile.get("username")
            username = str(username_raw) if isinstance(username_raw, str) else item.username
            refreshed_top_players.append(
                UserTopPlayerOut(
                    id=int(item.id),
                    username=username,
                    games_together=max(0, int(item.games_together)),
                )
            )
        game_stats = game_stats.model_copy(update={"top_players": refreshed_top_players})

    return UserStatsOut(
        rooms_created=max(0, safe_int(rooms_created.get(uid, 0))),
        games_in_my_rooms=max(0, safe_int(games_in_owned_rooms.get(uid, 0))),
        room_minutes=room_minutes,
        stream_minutes=stream_minutes,
        spectator_minutes=spectator_minutes,
        game=game_stats,
    )


async def emit_rooms_upsert(rid: int) -> None:
    from ..realtime.utils import get_rooms_brief, emit_rooms_upsert_safe

    r = get_redis()
    try:
        items = await get_rooms_brief(r, [rid])
        item = items[0] if items else None
    except Exception as e:
        log.exception("rooms.upsert.prepare_failed", rid=rid, err=type(e).__name__)
        return

    if not item:
        return

    try:
        await emit_rooms_upsert_safe(r, rid, item)
    except Exception as e:
        log.warning("rooms.upsert.emit_failed", rid=rid, err=type(e).__name__)


async def gc_room_after_delay(rid: int, delay_s: int | None = None) -> None:
    from ..realtime.utils import gc_empty_room

    if delay_s is None:
        from ..security.parameters import get_cached_settings
        delay_s = max(0, int(get_cached_settings().rooms_empty_ttl_seconds))

    await asyncio.sleep(max(0, delay_s))
    await gc_empty_room(rid)


def schedule_room_gc(rid: int, delay_s: int | None = None) -> None:
    asyncio.create_task(gc_room_after_delay(rid, delay_s))


async def gc_empty_room_and_emit(rid: int, *, expected_seq: int | None = None) -> None:
    from ..realtime.utils import gc_empty_room

    with suppress(Exception):
        await gc_empty_room(rid, expected_seq=expected_seq)


async def refresh_rooms_after(delay_s: int, reason: str) -> None:
    await asyncio.sleep(max(0, int(delay_s)))
    with suppress(Exception):
        await sio.emit("rooms_refresh", {"reason": reason}, namespace="/rooms")


async def broadcast_creator_rooms(uid: int, *, update_name: Optional[str] = None, avatar: Literal["keep", "set", "delete"] = "keep", avatar_name: Optional[str] = None) -> None:
    r = get_redis()
    ids = [int(x) for x in (await r.smembers(f"user:{uid}:rooms") or [])]
    if not ids:
        return

    try:
        async with r.pipeline() as p:
            for rid in ids:
                mapping: Dict[str, Any] = {}
                if update_name is not None:
                    mapping["creator_name"] = update_name
                if avatar == "set":
                    if avatar_name is None:
                        log.warning("rooms.creator.avatar_set_missing_name", uid=uid, rid=rid)
                    else:
                        mapping["creator_avatar_name"] = str(avatar_name)
                elif avatar == "delete":
                    await p.hdel(f"room:{rid}:params", "creator_avatar_name")
                if mapping:
                    await p.hset(f"room:{rid}:params", mapping=mapping)
            await p.execute()
    except Exception as e:
        log.warning("rooms.creator.batch_failed", uid=uid, err=type(e).__name__)

    for rid in ids:
        try:
            await emit_rooms_upsert(rid)
        except Exception as e:
            log.warning("rooms.upsert.iter_failed", rid=rid, err=type(e).__name__)


async def emit_room_profile_theme_sync(uid: int, theme_color: str | None, theme_icon: str | None) -> None:
    r = get_redis()
    try:
        raw_room_id = await r.get(f"user:{int(uid)}:room")
    except Exception:
        raw_room_id = None

    rid = int(raw_room_id) if raw_room_id else 0
    if rid <= 0:
        return

    try:
        normalized_color = theme_color.strip() if isinstance(theme_color, str) and theme_color.strip() else None
        normalized_icon = theme_icon.strip() if isinstance(theme_icon, str) and theme_icon.strip() else None
        if normalized_color:
            await r.hset(f"room:{rid}:user:{int(uid)}:info", mapping={"theme_color": normalized_color})
            if normalized_icon:
                await r.hset(f"room:{rid}:user:{int(uid)}:info", mapping={"theme_icon": normalized_icon})
            else:
                await r.hdel(f"room:{rid}:user:{int(uid)}:info", "theme_icon")
        else:
            await r.hdel(f"room:{rid}:user:{int(uid)}:info", "theme_color", "theme_icon")
    except Exception as exc:
        log.warning("room.profile_theme.cache_failed", rid=rid, uid=int(uid), err=type(exc).__name__)

    with suppress(Exception):
        await sio.emit(
            "profile_theme_sync",
            {
                "user_id": int(uid),
                "theme_color": theme_color if isinstance(theme_color, str) and theme_color.strip() else None,
                "theme_icon": theme_icon if isinstance(theme_icon, str) and theme_icon.strip() else None,
            },
            room=f"room:{rid}",
            namespace="/room",
        )


async def get_room_params_or_404(r, room_id: int) -> Dict[str, Any]:
    params = await r.hgetall(f"room:{room_id}:params")
    if not params:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="room_not_found")

    return params


async def get_room_game_runtime(r, room_id: int) -> Dict[str, Any]:
    async with r.pipeline() as p:
        await p.hgetall(f"room:{room_id}:game_state")
        await p.hgetall(f"room:{room_id}:game_seats")
        await p.smembers(f"room:{room_id}:game_players")
        await p.smembers(f"room:{room_id}:game_alive")
        raw_gstate, raw_seats, players_set, alive_set = await p.execute()
    phase = str(raw_gstate.get("phase") or "idle")

    try:
        head_uid = int(raw_gstate.get("head") or 0)
    except Exception:
        head_uid = 0

    seats_map: Dict[int, int] = {}
    for k, v in (raw_seats or {}).items():
        try:
            seats_map[int(k)] = int(v)
        except Exception:
            continue

    def _to_int_set(vals) -> set[int]:
        out: set[int] = set()
        for x in vals or []:
            try:
                out.add(int(x))
            except Exception:
                continue
        return out

    players = _to_int_set(players_set)
    alive_players = _to_int_set(alive_set)

    return {
        "phase": phase,
        "head": head_uid,
        "seats": seats_map,
        "players": players,
        "alive": alive_players,
    }


async def build_room_members_for_info(r, room_id: int) -> list[Dict[str, Any]]:
    from ..realtime.utils import get_profiles_snapshot

    order_raw = await r.zrange(f"room:{room_id}:positions", 0, -1)
    order_ids = [int(uid) for uid in order_raw]
    owner_raw = await r.get(f"room:{room_id}:screen_owner")
    screen_owner = int(owner_raw) if owner_raw else 0

    game_rt = await get_room_game_runtime(r, room_id)
    phase: str = game_rt["phase"]
    head_uid: int = game_rt["head"]
    seats_map: Dict[int, int] = game_rt["seats"]
    players: set[int] = game_rt["players"]
    alive_players: set[int] = game_rt["alive"]
    seen: set[int] = set(order_ids)
    all_ids: list[int] = list(order_ids)

    if phase != "idle" and head_uid and head_uid not in seen:
        all_ids.append(head_uid)
    seen.add(head_uid)
    extra_players = [uid for uid in players if uid not in seen]
    all_ids.extend(extra_players)
    if not all_ids:
        return []

    profiles = await get_profiles_snapshot(r, room_id)
    missing = [uid for uid in all_ids if str(uid) not in profiles]

    if missing:
        try:
            async with SessionLocal() as s:
                cached_profiles = await get_user_profiles_cached(s, missing)
                for uid, profile in cached_profiles.items():
                    profiles[str(uid)] = {
                        "username": profile.get("username"),
                        "avatar_name": profile.get("avatar_name"),
                    }
        except Exception:
            log.exception("room.info.extra_profiles_failed", rid=room_id)

    raw_members: list[Dict[str, Any]] = []
    for uid in all_ids:
        p = profiles.get(str(uid)) or {}
        role = None
        slot = None
        alive = None

        if phase != "idle":
            if uid == head_uid:
                role = "head"
            elif uid in players:
                role = "player"
                slot = seats_map.get(uid)
                alive = uid in alive_players
            else:
                role = "observer"

        raw_members.append(
            {
                "id": uid,
                "username": p.get("username"),
                "avatar_name": p.get("avatar_name"),
                "profile_role": p.get("role"),
                "screen": True if screen_owner and uid == screen_owner else None,
                "role": role,
                "slot": slot,
                "alive": alive,
            }
        )

    return raw_members


async def touch_user_last_login(db: AsyncSession, user_id: int) -> None:
    await db.execute(update(User).where(User.id == user_id).values(last_login_at=func.now()))
    await db.commit()


def validate_object_key_for_presign(key: str) -> None:
    if not key or not PRESIGN_KEY_RE.match(key):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_key")

    if not any(key.startswith(p) for p in PRESIGN_ALLOWED_PREFIXES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden_prefix")

    if ".." in key or "//" in key or key.endswith("/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_key")
