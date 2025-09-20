from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Any, Dict, Iterable, Mapping
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker
from .core.clients import get_redis
from .db import engine
from .models.room import Room

__all__ = [
    "to_redis",
    "apply_state",
    "get_room_snapshot",
    "get_occupancies",
    "gc_empty_room",
    "rate_limit",
    "rooms_index_add",
]

_sessionmaker = async_sessionmaker(bind=engine, expire_on_commit=False)


def to_redis(d: Mapping[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in d.items():
        if isinstance(v, bool):
            out[k] = "1" if v else "0"
        elif v is None:
            out[k] = ""
        else:
            out[k] = str(v)
    return out


def _to01(v: Any) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"
    s = str(v).strip().lower()
    return "1" if s in {"1", "true", "on", "yes"} else "0"


async def apply_state(r, rid: int, uid: int, data: Mapping[str, Any]) -> Dict[str, str]:
    m: Dict[str, str] = {}
    for k in ("mic", "cam", "speakers", "visibility"):
        if k in data:
            m[k] = _to01(data[k])
    if not m:
        return {}
    await r.hset(f"room:{rid}:user:{uid}:state", mapping=m)
    return m


async def get_room_snapshot(r, rid: int) -> Dict[str, Dict[str, str]]:
    ids = await r.smembers(f"room:{rid}:members")
    if not ids:
        return {}
    pipe = r.pipeline()
    for uid in ids:
        await pipe.hgetall(f"room:{rid}:user:{uid}:state")
    states = await pipe.execute()
    out: Dict[str, Dict[str, str]] = {}
    for uid, st in zip(ids, states):
        out[str(uid)] = st or {}
    return out


async def get_occupancies(r, rids: Iterable[int]) -> Dict[int, int]:
    ids = list(rids)
    pipe = r.pipeline()
    for rid in ids:
        await pipe.scard(f"room:{rid}:members")
    vals = await pipe.execute()
    return {rid: int(v or 0) for rid, v in zip(ids, vals)}


async def gc_empty_room(rid: int) -> bool:
    r = get_redis()
    if not await r.setnx(f"room:{rid}:gc_lock", "1"):
        return False
    await r.expire(f"room:{rid}:gc_lock", 20)
    await asyncio.sleep(10)
    if int(await r.scard(f"room:{rid}:members") or 0) > 0:
        return False

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
    await r.delete(f"room:{rid}:params")
    await r.zrem("rooms:index", str(rid))

    async with _sessionmaker() as s:
        rm = await s.get(Room, rid)
        if rm:
            await s.delete(rm)
            await s.commit()

    return True


async def rate_limit(key: str, *, limit: int, window_s: int) -> None:
    r = get_redis()
    async with r.pipeline(transaction=True) as pipe:
        await pipe.incr(key, 1)
        await pipe.expire(key, window_s)
        cnt, _ = await pipe.execute()
    if int(cnt) > limit:
        raise HTTPException(status_code=429, detail="rate_limited", headers={"Retry-After": str(window_s)})


async def rooms_index_add(r, *, rid: int, created_at_iso: str) -> None:
    try:
        dt = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
        score = int(dt.timestamp())
    except Exception:
        score = 0
    await r.zadd("rooms:index", {str(rid): score})
