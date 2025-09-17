from __future__ import annotations
import asyncio
from typing import Any, Dict
from sqlalchemy.ext.asyncio import async_sessionmaker
from ..db import engine
from ..core.clients import get_redis
from ..models.room import Room


_sessionmaker = async_sessionmaker(bind=engine, expire_on_commit=False)


def to01(v: Any) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"
    return "1" if str(v).strip().lower() in {"1", "true", "on", "yes"} else "0"


async def snapshot(r, rid: int) -> Dict[str, Dict[str, str]]:
    ids = await r.smembers(f"room:{rid}:members")
    out: Dict[str, Dict[str, str]] = {}
    for uid in ids or []:
        uid_str = str(uid)
        out[uid_str] = await r.hgetall(f"room:{rid}:user:{uid_str}:state")
    return out


async def apply_state(r, rid: int, uid: int, data: Dict[str, Any]) -> Dict[str, str]:
    m = {}
    for k in ("mic", "cam", "speakers", "visibility"):
        if k in data:
            m[k] = to01(data[k])
    if not m:
        return {}
    await r.hset(f"room:{rid}:user:{uid}:state", mapping=m)
    return m


async def broadcast_rooms_occupancy(r, rid: int) -> None:
    from .sio import sio
    occ = int(await r.scard(f"room:{rid}:members") or 0)
    await sio.emit("rooms_occupancy", {"id": rid, "occupancy": occ}, namespace="/rooms")


async def gc_empty_room(rid: int):
    from .sio import sio
    r = get_redis()
    if not await r.setnx(f"room:{rid}:gc_lock", "1"):
        return
    await r.expire(f"room:{rid}:gc_lock", 20)

    await asyncio.sleep(10)
    if int(await r.scard(f"room:{rid}:members") or 0) > 0:
        return

    await r.delete(f"room:{rid}:params")
    await r.srem("rooms:index", rid)

    async def _del_scan(pattern: str, count: int = 200):
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor=cursor, match=pattern, count=count)
            if keys:
                await r.delete(*keys)
            if cursor == 0:
                break

    await _del_scan(f"room:{rid}:user:*:state")
    await _del_scan(f"room:{rid}:member:*")
    await r.delete(f"room:{rid}:members")

    async with _sessionmaker() as s:
        rm = await s.get(Room, rid)
        if rm:
            await s.delete(rm)
            await s.commit()

    await sio.emit("rooms_remove", {"id": rid}, namespace="/rooms")
