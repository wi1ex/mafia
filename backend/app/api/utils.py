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
from typing import Optional, Dict, Any, Literal, Sequence, Iterable, cast
from fastapi import HTTPException, status, Header
from sqlalchemy import update, func, select, or_, and_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.clients import get_redis
from ..core.db import SessionLocal
from ..core.settings import settings
from ..models.game import Game
from ..models.log import AppLog
from ..models.room import Room
from ..models.friend import FriendLink
from ..models.notif import Notif
from ..models.sanction import UserSanction
from ..models.user import User
from ..models.update import SiteUpdate, UpdateRead
from ..schemas.admin import SiteSettingsOut, GameSettingsOut, RegistrationsPoint, AdminRoomUserStat, AdminSanctionOut
from ..schemas.room import GameParams
from ..realtime.sio import sio
from ..realtime.utils import get_profiles_snapshot, get_rooms_brief, gc_empty_room
from ..services.minio import delete_avatars
from ..security.parameters import get_cached_settings

__all__ = [
    "SANCTION_TIMEOUT",
    "SANCTION_BAN",
    "SANCTION_SUSPEND",
    "USERS_SORT_DEFAULT",
    "TIMED_KINDS",
    "serialize_game_for_redis",
    "game_from_redis_to_model",
    "emit_rooms_upsert",
    "broadcast_creator_rooms",
    "get_room_game_runtime",
    "build_room_members_for_info",
    "get_room_params_or_404",
    "touch_user_last_login",
    "touch_user_last_visit",
    "touch_user_online",
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
    "calc_total_stream_seconds",
    "calc_stream_seconds_in_range",
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
    "aggregate_user_room_stats",
    "normalize_users_sort",
    "fetch_friends_count_for_users",
    "fetch_sanction_counts_for_users",
    "user_sort_metric",
    "compute_duration_seconds",
    "is_sanction_active",
    "fetch_active_sanction",
    "fetch_active_sanctions",
    "fetch_sanctions_for_users",
    "build_admin_sanction_out",
    "emit_sanctions_update",
    "refresh_rooms_after",
    "ensure_room_access_allowed",
    "ensure_profile_changes_allowed",
    "is_protected_admin",
    "ensure_admin_target_allowed",
    "set_user_deleted",
    "force_logout_user",
    "check_sanctions_expired",
    "format_duration_parts",
    "normalize_username",
    "normalize_password",
    "find_user_by_username",
    "generate_user_id",
    "init_updates_read",
    "require_bot_token",
    "pair",
    "load_link",
    "emit_notify",
    "emit_friends_update",
]

log = structlog.get_logger()

PRESIGN_ALLOWED_PREFIXES: tuple[str, ...] = ("avatars/",)
PRESIGN_KEY_RE = re.compile(r"^[a-zA-Z0-9._/-]{3,256}$")
STREAM_LOG_RE = re.compile(r"room_id=(\d+)\s+target_user=(\d+)")
BOT_USERNAME_RE = re.compile(r"^[a-zA-Zа-яА-Я0-9._\-()]{2,20}$")
PWD_CTRL_RE = re.compile(r"[\x00-\x1F\x7F]")

SANCTION_TIMEOUT = "timeout"
SANCTION_BAN = "ban"
SANCTION_SUSPEND = "suspend"
USERS_SORT_DEFAULT = "registered_at"
USERS_SORT_ALLOWED = {
    USERS_SORT_DEFAULT,
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
TIMED_KINDS = {SANCTION_TIMEOUT, SANCTION_SUSPEND}


def normalize_users_sort(sort_by: str | None) -> str:
    value = (sort_by or "").strip().lower()
    if value in USERS_SORT_ALLOWED:
        return value
    return USERS_SORT_DEFAULT


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


def user_sort_metric(*, sort_by: str, uid: int, friends_count: dict[int, int], rooms_created: dict[int, int], room_seconds: dict[int, int], stream_seconds: dict[int, int], games_played: dict[int, int], games_hosted: dict[int, int], spectator_seconds: dict[int, int], sanction_counts: dict[int, dict[str, int]]) -> int:
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
    out = {
        SANCTION_TIMEOUT: None,
        SANCTION_BAN: None,
        SANCTION_SUSPEND: None,
    }
    for row in items:
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


def format_duration_parts(months: int, days: int, hours: int, minutes: int) -> str:
    parts: list[str] = []
    if months:
        parts.append(f"{months} \u043c\u0435\u0441")
    if days:
        parts.append(f"{days} \u0434")
    if hours:
        parts.append(f"{hours} \u0447")
    if minutes or not parts:
        parts.append(f"{minutes} \u043c\u0438\u043d")

    return " ".join(parts)


def normalize_username(raw: str) -> str:
    out = unicodedata.normalize("NFKC", raw or "").strip()
    if not BOT_USERNAME_RE.match(out):
        raise HTTPException(status_code=422, detail="invalid_username_format")

    return out


def normalize_password(raw: str) -> str:
    pwd = str(raw or "")
    if not pwd.strip():
        raise HTTPException(status_code=422, detail="invalid_password")

    if len(pwd) < 8 or len(pwd) > 32:
        raise HTTPException(status_code=422, detail="invalid_password")

    if PWD_CTRL_RE.search(pwd):
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


async def ensure_room_access_allowed(db: AsyncSession, user_id: int) -> None:
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
    try:
        uid = int(user_id or 0)
    except Exception:
        return False

    try:
        protected_uid = int(getattr(settings, "PROTECTED_ADMIN_USER_ID", 0) or 0)
    except Exception:
        protected_uid = 0

    return 0 < protected_uid == uid


def ensure_admin_target_allowed(user: User) -> None:
    if is_protected_admin(getattr(user, "id", 0)):
        raise HTTPException(status_code=403, detail="protected_user")


async def set_user_deleted(session: AsyncSession, user_id: int, *, deleted: bool) -> User:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    user = cast(User, user)
    was_deleted = user.deleted_at is not None
    if deleted:
        new_username = f"deleted_{int(user.id)}"
        user.username = new_username
        user.avatar_name = None
        user.telegram_id = None
    elif was_deleted:
        user.username = f"user_{int(user.id)}"

    if deleted:
        user.deleted_at = datetime.now(timezone.utc)
    else:
        user.deleted_at = None

    await session.commit()
    await session.refresh(user)

    if deleted:
        with suppress(Exception):
            delete_avatars(int(user.id))
        with suppress(Exception):
            await broadcast_creator_rooms(int(user.id), update_name=user.username, avatar="delete")
    elif was_deleted:
        with suppress(Exception):
            await broadcast_creator_rooms(int(user.id), update_name=user.username)

    return user


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
    if next_timeout_ts == prev_timeout_ts and next_suspend_ts == prev_suspend_ts:
        return

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


def serialize_game_for_redis(game_dict: Dict[str, Any]) -> Dict[str, str]:
    nominate_mode = str(game_dict.get("nominate_mode") or "players")
    if nominate_mode not in ("players", "head"):
        nominate_mode = "players"
    return {
        "mode": str(game_dict["mode"]),
        "format": str(game_dict["format"]),
        "spectators_limit": str(int(game_dict["spectators_limit"])),
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
    nominate_mode = str(raw_game.get("nominate_mode") or "players")
    if nominate_mode not in ("players", "head"):
        nominate_mode = "players"
    return GameParams(
        mode=(raw_game.get("mode") or "normal"),
        format=(raw_game.get("format") or "hosted"),
        spectators_limit=int(raw_game.get("spectators_limit") or 0),
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
    return SiteSettingsOut(
        registration_enabled=bool(row.registration_enabled),
        rooms_can_create=bool(row.rooms_can_create),
        rooms_can_enter=bool(row.rooms_can_enter),
        games_can_start=bool(row.games_can_start),
        streams_can_start=bool(row.streams_can_start),
        verification_restrictions=bool(row.verification_restrictions),
        rooms_limit_global=int(row.rooms_limit_global),
        rooms_limit_per_user=int(row.rooms_limit_per_user),
        rooms_empty_ttl_seconds=int(row.rooms_empty_ttl_seconds),
        rooms_single_ttl_minutes=int(row.rooms_single_ttl_minutes),
        season_start_game_number=int(row.season_start_game_number),
    )


def game_settings_out(row) -> GameSettingsOut:
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
    rows = await session.execute(
        select(func.date_trunc("day", User.registered_at).label("day"), func.count(User.id))
        .where(User.registered_at >= start_dt, User.registered_at < end_dt)
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
    rows = await session.execute(select(func.date_trunc("month", User.registered_at).label("month"), func.count(User.id)).group_by("month").order_by("month"))
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


async def calc_total_stream_seconds(session: AsyncSession) -> int:
    first_log = await session.scalar(select(func.min(AppLog.created_at)).where(AppLog.action.in_(("stream_start", "stream_stop"))))
    if first_log:
        now = datetime.now(timezone.utc)
        return await calc_stream_seconds_in_range(session, first_log, now)

    total_stream_seconds = 0
    rooms_rows = await session.execute(select(Room.created_at, Room.deleted_at, Room.screen_time))
    for _created_at, _deleted_at, screen_time in rooms_rows.all():
        if isinstance(screen_time, dict):
            for v in screen_time.values():
                try:
                    total_stream_seconds += int(v or 0)
                except Exception:
                    continue

    return total_stream_seconds


def parse_stream_log_details(details: str) -> tuple[int, int] | None:
    if not details:
        return None

    match = STREAM_LOG_RE.search(details)
    if not match:
        return None

    try:
        rid = int(match.group(1))
        uid = int(match.group(2))
    except Exception:
        return None

    if rid <= 0 or uid <= 0:
        return None

    return rid, uid


async def calc_stream_seconds_in_range(session: AsyncSession, start_dt: datetime, end_dt: datetime) -> int:
    rows = await session.execute(
        select(AppLog.action, AppLog.details, AppLog.created_at)
        .where(
            AppLog.action.in_(("stream_start", "stream_stop")),
            AppLog.created_at >= start_dt,
            AppLog.created_at < end_dt,
        )
        .order_by(AppLog.created_at)
    )
    active: dict[tuple[int, int], datetime] = {}
    total_seconds = 0
    for action, details, created_at in rows.all():
        parsed = parse_stream_log_details(str(details or ""))
        if not parsed:
            continue
        key = (parsed[0], parsed[1])
        if action == "stream_start":
            active[key] = created_at
            continue
        if action == "stream_stop":
            start_at = active.pop(key, None) or start_dt
            seg_start = start_at if start_at > start_dt else start_dt
            seg_end = created_at if created_at < end_dt else end_dt
            if seg_end > seg_start:
                total_seconds += int((seg_end - seg_start).total_seconds())
    if active:
        for start_at in active.values():
            seg_start = start_at if start_at > start_dt else start_dt
            if end_dt > seg_start:
                total_seconds += int((end_dt - seg_start).total_seconds())

    return total_seconds


def online_cutoff_ts(now_ts: int | None = None) -> int:
    ttl = settings.ONLINE_TTL_SECONDS
    if now_ts is None:
        now_ts = int(time())

    return int(now_ts) - ttl


async def touch_user_online(r, user_id: int) -> None:
    try:
        uid = int(user_id)
    except Exception:
        return

    if uid <= 0:
        return

    await r.zadd("online:users:seen", {str(uid): int(time())})


async def prune_online_users(r, cutoff_ts: int) -> None:
    await r.zremrangebyscore("online:users:seen", "-inf", int(cutoff_ts) - 1)


async def fetch_active_rooms_stats(r) -> tuple[int, int]:
    rids = await r.zrange("rooms:index", 0, -1)
    active_rooms = 0
    active_room_users = 0
    if rids:
        async with r.pipeline() as p:
            for rid in rids:
                await p.scard(f"room:{int(rid)}:members")
            counts = await p.execute()
        for cnt in counts:
            try:
                val = int(cnt or 0)
            except Exception:
                val = 0
            if val > 0:
                active_rooms += 1
                active_room_users += val

    return active_rooms, active_room_users


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


async def fetch_user_avatar_map(session: AsyncSession, user_ids: set[int]) -> dict[int, str | None]:
    avatar_map: dict[int, str | None] = {}
    if not user_ids:
        return avatar_map

    rows_users = await session.execute(select(User.id, User.avatar_name).where(User.id.in_(user_ids)))
    for uid, avatar_name in rows_users.all():
        try:
            avatar_map[int(uid)] = avatar_name
        except Exception:
            continue

    return avatar_map


async def fetch_user_name_avatar_maps(session: AsyncSession, user_ids: set[int]) -> tuple[dict[int, str | None], dict[int, str | None]]:
    name_map: dict[int, str | None] = {}
    avatar_map: dict[int, str | None] = {}
    if not user_ids:
        return name_map, avatar_map

    rows_users = await session.execute(select(User.id, User.username, User.avatar_name).where(User.id.in_(user_ids)))
    for uid, username, avatar_name in rows_users.all():
        try:
            uid_int = int(uid)
        except Exception:
            continue
        name_map[uid_int] = username
        avatar_map[uid_int] = avatar_name

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
    try:
        spectators_limit = int(game.get("spectators_limit") or 0)
    except Exception:
        spectators_limit = 0

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


def build_room_user_stats(raw_map: dict | None, name_map: dict[int, str | None]) -> list[AdminRoomUserStat]:
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
            items.append(AdminRoomUserStat(id=uid, username=name_map.get(uid), minutes=minutes))
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
        raw = await p.execute()

    room_chunks: dict[int, dict[str, Any]] = {}
    join_reqs: list[tuple[int, str]] = []
    step = 7
    for idx, rid in enumerate(room_ids):
        base = idx * step
        visitors_raw = raw[base]
        members_raw = raw[base + 1]
        spectators_raw = raw[base + 2]
        spectators_join_raw = raw[base + 3]
        screen_raw = raw[base + 4]
        screen_owner_raw = raw[base + 5]
        screen_started_raw = raw[base + 6]

        members = set(members_raw or [])
        for uid in members:
            join_reqs.append((rid, str(uid)))

        room_chunks[rid] = {
            "visitors": _map_seconds(visitors_raw),
            "members": members,
            "spectators": _map_seconds(spectators_raw),
            "spectators_join": _map_seconds(spectators_join_raw),
            "streams": _map_seconds(screen_raw),
            "screen_owner": _parse_int(screen_owner_raw),
            "screen_started_at": _parse_int(screen_started_raw),
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
        }

    return out


async def aggregate_user_room_stats(session: AsyncSession, ids: list[int]) -> tuple[dict[int, int], dict[int, int], dict[int, int], dict[int, int], dict[int, int], dict[int, int]]:
    rooms_created: dict[int, int] = {uid: 0 for uid in ids}
    room_seconds: dict[int, int] = {uid: 0 for uid in ids}
    stream_seconds: dict[int, int] = {uid: 0 for uid in ids}
    spectator_seconds: dict[int, int] = {uid: 0 for uid in ids}
    games_played: dict[int, int] = {uid: 0 for uid in ids}
    games_hosted: dict[int, int] = {uid: 0 for uid in ids}

    if not ids:
        return rooms_created, room_seconds, stream_seconds, spectator_seconds, games_played, games_hosted

    counts = await session.execute(select(Room.creator, func.count(Room.id)).where(Room.creator.in_(ids)).group_by(Room.creator))
    for creator, cnt in counts.all():
        try:
            rooms_created[int(creator)] = int(cnt or 0)
        except Exception:
            continue

    id_strs = [str(i) for i in ids]
    scan_all = len(ids) > 200
    if scan_all:
        room_rows = await session.execute(select(Room.visitors, Room.screen_time, Room.spectators_time))
    else:
        room_filters = [Room.creator.in_(ids)]
        room_filters += [Room.visitors.has_key(i) for i in id_strs]
        room_filters += [Room.screen_time.has_key(i) for i in id_strs]
        room_filters += [Room.spectators_time.has_key(i) for i in id_strs]
        room_rows = await session.execute(select(Room.visitors, Room.screen_time, Room.spectators_time).where(or_(*room_filters)))

    id_set = set(ids)
    for visitors, screen_time, spectators_time in room_rows.all():
        if isinstance(visitors, dict):
            for k, v in visitors.items():
                try:
                    uid = int(k)
                except Exception:
                    continue
                if uid in id_set:
                    try:
                        room_seconds[uid] += int(v or 0)
                    except Exception:
                        continue

        if isinstance(screen_time, dict):
            for k, v in screen_time.items():
                try:
                    uid = int(k)
                except Exception:
                    continue
                if uid in id_set:
                    try:
                        stream_seconds[uid] += int(v or 0)
                    except Exception:
                        continue

        if isinstance(spectators_time, dict):
            for k, v in spectators_time.items():
                try:
                    uid = int(k)
                except Exception:
                    continue
                if uid in id_set:
                    try:
                        spectator_seconds[uid] += int(v or 0)
                    except Exception:
                        continue

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


async def emit_rooms_upsert(rid: int) -> None:
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
        await sio.emit("rooms_upsert",
                       item,
                       namespace="/rooms")
    except Exception as e:
        log.warning("rooms.upsert.emit_failed", rid=rid, err=type(e).__name__)


async def gc_room_after_delay(rid: int, delay_s: int | None = None) -> None:
    if delay_s is None:
        delay_s = max(0, int(get_cached_settings().rooms_empty_ttl_seconds))

    await asyncio.sleep(max(0, delay_s))

    removed = await gc_empty_room(rid)
    if removed:
        await sio.emit("rooms_remove",
                       {"id": rid},
                       namespace="/rooms")


def schedule_room_gc(rid: int, delay_s: int | None = None) -> None:
    asyncio.create_task(gc_room_after_delay(rid, delay_s))


async def gc_empty_room_and_emit(rid: int, *, expected_seq: int | None = None) -> None:
    with suppress(Exception):
        removed = await gc_empty_room(rid, expected_seq=expected_seq)
        if removed:
            await sio.emit("rooms_remove", {"id": rid}, namespace="/rooms")


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


async def get_room_params_or_404(r, room_id: int) -> Dict[str, Any]:
    params = await r.hgetall(f"room:{room_id}:params")
    if not params:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="room_not_found")

    return params


async def get_room_game_runtime(r, room_id: int) -> Dict[str, Any]:
    raw_gstate = await r.hgetall(f"room:{room_id}:game_state")
    raw_seats = await r.hgetall(f"room:{room_id}:game_seats")
    players_set = await r.smembers(f"room:{room_id}:game_players")
    alive_set = await r.smembers(f"room:{room_id}:game_alive")
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
                for uid in missing:
                    u = await s.get(User, uid)
                    if u:
                        profiles[str(uid)] = {"username": u.username, "avatar_name": u.avatar_name}
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


async def touch_user_last_visit(db: AsyncSession, user_id: int) -> None:
    await db.execute(update(User).where(User.id == user_id).values(last_visit_at=func.now()))
    await db.commit()


def validate_object_key_for_presign(key: str) -> None:
    if not key or not PRESIGN_KEY_RE.match(key):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_key")

    if not any(key.startswith(p) for p in PRESIGN_ALLOWED_PREFIXES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden_prefix")

    if ".." in key or "//" in key or key.endswith("/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_key")
