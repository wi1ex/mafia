from __future__ import annotations
from typing import Optional, Dict, Any
import structlog
from ..core.clients import get_redis
from ..realtime.utils import get_room_brief
from ..realtime.sio import sio
from ..schemas.room import GameParams

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


async def broadcast_creator_rooms(uid: int, update_name: Optional[str] = None) -> None:
    r = get_redis()
    ids = [int(x) for x in (await r.smembers(f"user:{uid}:rooms") or [])]
    if not ids:
        return

    if update_name is not None:
        try:
            async with r.pipeline() as p:
                for rid in ids:
                    await p.hset(f"room:{rid}:params", mapping={"creator_name": update_name})
                await p.execute()
        except Exception as e:
            log.warning("rooms.creator_name.batch_failed", uid=uid, err=type(e).__name__)

    for rid in ids:
        try:
            await emit_rooms_upsert(rid)
        except Exception as e:
            log.warning("rooms.upsert.iter_failed", rid=rid, err=type(e).__name__)
