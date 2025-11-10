from __future__ import annotations
import structlog
from typing import Optional, Dict, Any, cast, Literal
from ..core.db import SessionLocal
from ..core.clients import get_redis
from ..models.user import User
from ..realtime.sio import sio
from ..schemas.room import GameParams

__all__ = [
    "serialize_game_for_redis",
    "game_from_redis_to_model",
    "get_room_brief",
    "emit_rooms_upsert",
    "broadcast_creator_rooms",
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


async def get_room_brief(r, rid: int) -> Optional[dict]:
    fields = ("id", "title", "user_limit", "creator", "creator_name", "creator_avatar_name", "created_at", "privacy")
    _id, title, user_limit, creator, creator_name, creator_avatar_name, created_at, privacy = await r.hmget(f"room:{rid}:params", *fields)
    if not (_id and title and user_limit and creator and creator_name and created_at):
        return None

    occ = int(await r.scard(f"room:{rid}:members") or 0)
    if creator_avatar_name is None:
        async with SessionLocal() as s:
            u = await s.get(User, int(creator))
            creator_avatar_name = cast(Optional[str], u.avatar_name) if u else None

    return {
        "id": int(_id),
        "title": str(title),
        "user_limit": int(user_limit),
        "creator": int(creator),
        "creator_name": str(creator_name),
        "creator_avatar_name": creator_avatar_name,
        "created_at": str(created_at),
        "privacy": str(privacy or "open"),
        "occupancy": occ,
    }


async def emit_rooms_upsert(rid: int) -> None:
    r = get_redis()
    try:
        item = await get_room_brief(r, rid)
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
