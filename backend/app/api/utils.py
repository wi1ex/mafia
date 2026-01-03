from __future__ import annotations
import asyncio
import calendar
import re
import structlog
from datetime import date, datetime, timezone, timedelta
from typing import Optional, Dict, Any, Literal, Sequence
from fastapi import HTTPException, status
from sqlalchemy import update, func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.clients import get_redis
from ..core.db import SessionLocal
from ..models.game import Game
from ..models.log import AppLog
from ..models.room import Room
from ..models.user import User
from ..schemas.admin import SiteSettingsOut, GameSettingsOut, RegistrationsPoint, AdminRoomUserStat
from ..schemas.room import GameParams
from ..realtime.sio import sio
from ..realtime.utils import get_profiles_snapshot, get_rooms_brief, gc_empty_room
from ..security.parameters import get_cached_settings

__all__ = [
    "serialize_game_for_redis",
    "game_from_redis_to_model",
    "emit_rooms_upsert",
    "broadcast_creator_rooms",
    "get_room_game_runtime",
    "build_room_members_for_info",
    "get_room_params_or_404",
    "touch_user_last_login",
    "touch_user_last_visit",
    "validate_object_key_for_presign",
    "parse_month_range",
    "parse_day_range",
    "site_settings_out",
    "game_settings_out",
    "schedule_room_gc",
    "normalize_pagination",
    "build_registrations_series",
    "calc_total_stream_seconds",
    "calc_stream_seconds_in_range",
    "fetch_active_rooms_stats",
    "fetch_online_users_count",
    "fetch_user_avatar_map",
    "fetch_user_name_avatar_maps",
    "collect_room_user_ids",
    "parse_room_game_params",
    "build_room_user_stats",
    "sum_room_stream_seconds",
    "aggregate_user_room_stats",
]

log = structlog.get_logger()

PRESIGN_ALLOWED_PREFIXES: tuple[str, ...] = ("avatars/",)
PRESIGN_KEY_RE = re.compile(r"^[a-zA-Z0-9._/-]{3,256}$")
STREAM_LOG_RE = re.compile(r"room_id=(\d+)\s+target_user=(\d+)")


def serialize_game_for_redis(game_dict: Dict[str, Any]) -> Dict[str, str]:
    return {
        "mode": str(game_dict["mode"]),
        "format": str(game_dict["format"]),
        "spectators_limit": str(int(game_dict["spectators_limit"])),
        "break_at_zero": "1" if raw_bool(game_dict.get("break_at_zero"), True) else "0",
        "lift_at_zero": "1" if raw_bool(game_dict.get("lift_at_zero"), True) else "0",
        "lift_3x": "1" if raw_bool(game_dict.get("lift_3x"), True) else "0",
    }


def raw_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip() in ("1", "true", "True")


def game_from_redis_to_model(raw_game: Dict[str, Any]) -> GameParams:
    return GameParams(
        mode=(raw_game.get("mode") or "normal"),
        format=(raw_game.get("format") or "hosted"),
        spectators_limit=int(raw_game.get("spectators_limit") or 0),
        break_at_zero=raw_bool(raw_game.get("break_at_zero"), True),
        lift_at_zero=raw_bool(raw_game.get("lift_at_zero"), True),
        lift_3x=raw_bool(raw_game.get("lift_3x"), True),
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
        rooms_limit_global=int(row.rooms_limit_global),
        rooms_limit_per_user=int(row.rooms_limit_per_user),
        rooms_empty_ttl_seconds=int(row.rooms_empty_ttl_seconds),
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


async def calc_total_stream_seconds(session: AsyncSession) -> int:
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


async def fetch_online_users_count(r) -> int:
    return int(await r.scard("online:users") or 0)


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
    try:
        spectators_limit = int(game.get("spectators_limit") or 0)
    except Exception:
        spectators_limit = 0

    return {
        "mode": game_mode,
        "format": game_format,
        "spectators_limit": spectators_limit,
        "break_at_zero": raw_bool(game.get("break_at_zero"), True),
        "lift_at_zero": raw_bool(game.get("lift_at_zero"), True),
        "lift_3x": raw_bool(game.get("lift_3x"), True),
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

    role_filters = [Game.roles.has_key(i) for i in id_strs]
    if role_filters:
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
