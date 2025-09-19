from __future__ import annotations
import asyncio
from typing import Any, Dict
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker
from .core.clients import get_redis
from .db import engine
from .models.room import Room
from .realtime.sio import sio

__all__ = ["apply_state", "broadcast_rooms_occupancy", "gc_empty_room", "to_redis", "serialize_room", "rate_limit_create_room"]

_sessionmaker = async_sessionmaker(bind=engine, expire_on_commit=False)


def _to01(v: Any) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"
    s = str(v).strip().lower()
    return "1" if s in {"1", "true", "on", "yes"} else "0"


async def apply_state(r, rid: int, uid: int, data: Dict[str, Any]) -> Dict[str, str]:
    m: Dict[str, str] = {}
    for k in ("mic", "cam", "speakers", "visibility"):
        if k in data:
            m[k] = _to01(data[k])
    if not m:
        return {}
    await r.hset(f"room:{rid}:user:{uid}:state", mapping=m)
    return m


async def broadcast_rooms_occupancy(r, rid: int) -> None:
    occ = int(await r.scard(f"room:{rid}:members") or 0)
    await sio.emit("rooms_occupancy", {"id": rid, "occupancy": occ}, namespace="/rooms")


async def gc_empty_room(rid: int) -> None:
    r = get_redis()
    if not await r.setnx(f"room:{rid}:gc_lock", "1"):
        return
    await r.expire(f"room:{rid}:gc_lock", 20)

    await asyncio.sleep(10)
    if int(await r.scard(f"room:{rid}:members") or 0) > 0:
        return

    await r.delete(f"room:{rid}:params")

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


def to_redis(d: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in d.items():
        if isinstance(v, bool):
            out[k] = "1" if v else "0"
        elif v is None:
            out[k] = ""
        else:
            out[k] = str(v)
    return out


def serialize_room(room: Room, *, occupancy: int) -> Dict[str, Any]:
    return {
        "id": room.id,
        "title": room.title,
        "user_limit": room.user_limit,
        "is_private": room.is_private,
        "creator": room.creator,
        "created_at": room.created_at.isoformat(),
        "occupancy": occupancy,
    }


async def rate_limit_create_room(user_id: int, limit: int = 5, window_s: int = 60) -> None:
    r = get_redis()
    key = f"rl:create_room:{user_id}"

    async with r.pipeline(transaction=True) as pipe:
        await pipe.incr(key, 1)
        await pipe.expire(key, window_s)
        cnt, _ = await pipe.execute()

    if int(cnt) > limit:
        raise HTTPException(status_code=429, detail="rate_limited_create_room", headers={"Retry-After": str(window_s)})
