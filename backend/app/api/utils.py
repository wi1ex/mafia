from __future__ import annotations
from typing import Optional
import structlog
from ..core.clients import get_redis
from ..realtime.utils import get_room_brief
from ..realtime.sio import sio

log = structlog.get_logger()


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
        await sio.emit("rooms_upsert", item, namespace="/rooms")
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
