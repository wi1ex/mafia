from __future__ import annotations
import structlog
from typing import Optional, Dict, Any, Literal
from ..core.clients import get_redis
from ..schemas.room import GameParams
from ..realtime.sio import sio
from ..realtime.utils import get_profiles_snapshot, get_rooms_brief

__all__ = [
    "serialize_game_for_redis",
    "game_from_redis_to_model",
    "emit_rooms_upsert",
    "broadcast_creator_rooms",
    "get_room_game_runtime",
    "build_room_members_for_info",
]

log = structlog.get_logger()


def serialize_game_for_redis(game_dict: Dict[str, Any]) -> Dict[str, str]:
    return {
        "mode": str(game_dict["mode"]),
        "format": str(game_dict["format"]),
        "spectators_limit": str(int(game_dict["spectators_limit"])),
        "vote_at_zero": "1" if game_dict["vote_at_zero"] else "0",
        "vote_three": "1" if game_dict["vote_three"] else "0",
        "speech30_at_3_fouls": "1" if game_dict["speech30_at_3_fouls"] else "0",
        "extra30_at_2_fouls": "1" if game_dict["extra30_at_2_fouls"] else "0",
    }


def game_from_redis_to_model(raw_game: Dict[str, Any]) -> GameParams:
    def b(v: Any, d: bool) -> bool:
        if v is None:
            return d

        return str(v).strip() in ("1", "true", "True")

    return GameParams(
        mode=(raw_game.get("mode") or "normal"),
        format=(raw_game.get("format") or "hosted"),
        spectators_limit=int(raw_game.get("spectators_limit") or 0),
        vote_at_zero=b(raw_game.get("vote_at_zero"), True),
        vote_three=b(raw_game.get("vote_three"), True),
        speech30_at_3_fouls=b(raw_game.get("speech30_at_3_fouls"), True),
        extra30_at_2_fouls=b(raw_game.get("extra30_at_2_fouls"), True),
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


async def broadcast_creator_rooms(uid: int, *, update_name: Optional[str] = None, avatar: Literal["keep", "set", "delete"] = "keep", avatar_name: Optional[str] = None, ) -> None:
    r = get_redis()
    ids = [int(x) for x in (await r.smembers(f"user:{uid}:rooms") or [])]
    if not ids:
        return

    try:
        async with r.pipeline() as p:
            for rid in ids:
                mp = {}
                if update_name is not None:
                    mp["creator_name"] = update_name

                if avatar == "set":
                    if avatar_name is None:
                        log.warning("rooms.creator.avatar_set_missing_name", uid=uid, rid=rid)
                    else:
                        mp["creator_avatar_name"] = str(avatar_name)
                elif avatar == "delete":
                    await p.hdel(f"room:{rid}:params", "creator_avatar_name")

                if mp:
                    await p.hset(f"room:{rid}:params", mapping=mp)
            await p.execute()
    except Exception as e:
        log.warning("rooms.creator.batch_failed", uid=uid, err=type(e).__name__)

    for rid in ids:
        try:
            await emit_rooms_upsert(rid)
        except Exception as e:
            log.warning("rooms.upsert.iter_failed", rid=rid, err=type(e).__name__)


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
    profiles = await get_profiles_snapshot(r, room_id)
    game_rt = await get_room_game_runtime(r, room_id)
    phase: str = game_rt["phase"]
    head_uid: int = game_rt["head"]
    seats_map: Dict[int, int] = game_rt["seats"]
    players: set[int] = game_rt["players"]
    alive_players: set[int] = game_rt["alive"]

    raw_members: list[Dict[str, Any]] = []
    for uid in order_ids:
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
