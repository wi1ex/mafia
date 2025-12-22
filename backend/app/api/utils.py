from __future__ import annotations
import asyncio
import calendar
import re
import structlog
from datetime import date, datetime, timezone, timedelta
from typing import Optional, Dict, Any, Literal
from fastapi import HTTPException, status
from sqlalchemy import update, func
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.clients import get_redis
from ..core.db import SessionLocal
from ..models.user import User
from ..schemas.admin import SiteSettingsOut, GameSettingsOut
from ..schemas.room import GameParams
from ..realtime.sio import sio
from ..realtime.utils import get_profiles_snapshot, get_rooms_brief, gc_empty_room

__all__ = [
    "serialize_game_for_redis",
    "game_from_redis_to_model",
    "emit_rooms_upsert",
    "broadcast_creator_rooms",
    "get_room_game_runtime",
    "build_room_members_for_info",
    "get_room_params_or_404",
    "touch_user_last_login",
    "validate_object_key_for_presign",
    "parse_month_range",
    "parse_day_range",
    "site_settings_out",
    "game_settings_out",
    "schedule_room_gc",
]

log = structlog.get_logger()

PRESIGN_ALLOWED_PREFIXES: tuple[str, ...] = ("avatars/",)
PRESIGN_KEY_RE = re.compile(r"^[a-zA-Z0-9._/-]{3,256}$")


def serialize_game_for_redis(game_dict: Dict[str, Any]) -> Dict[str, str]:
    return {
        "mode": str(game_dict["mode"]),
        "format": str(game_dict["format"]),
        "spectators_limit": str(int(game_dict["spectators_limit"])),
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
        games_can_start=bool(row.games_can_start),
        rooms_limit_global=int(row.rooms_limit_global),
        rooms_limit_per_user=int(row.rooms_limit_per_user),
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


async def gc_room_after_delay(rid: int, delay_s: int = 12) -> None:
    await asyncio.sleep(delay_s)
    removed = await gc_empty_room(rid)
    if removed:
        await sio.emit("rooms_remove",
                       {"id": rid},
                       namespace="/rooms")


def schedule_room_gc(rid: int, delay_s: int = 12) -> None:
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


def validate_object_key_for_presign(key: str) -> None:
    if not key or not PRESIGN_KEY_RE.match(key):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_key")

    if not any(key.startswith(p) for p in PRESIGN_ALLOWED_PREFIXES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden_prefix")

    if ".." in key or "//" in key or key.endswith("/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_key")
