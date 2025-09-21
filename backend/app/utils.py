from __future__ import annotations
import asyncio
from time import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping
from fastapi import HTTPException
from redis import WatchError
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
    "join_room_atomic",
    "leave_room_atomic",
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


async def rate_limit(key: str, *, limit: int, window_s: int) -> None:
    r = get_redis()
    async with r.pipeline(transaction=True) as pipe:
        await pipe.incr(key, 1)
        await pipe.expire(key, window_s)
        cnt, _ = await pipe.execute()
    if int(cnt) > limit:
        raise HTTPException(status_code=429, detail="rate_limited", headers={"Retry-After": str(window_s)})


async def gc_empty_room(rid: int, *, expected_seq: int | None = None) -> bool:
    r = get_redis()

    ts1 = await r.get(f"room:{rid}:empty_since")
    if not ts1:
        return False

    ts1_i = int(ts1 if isinstance(ts1, (int, str)) else ts1.decode())
    real_now = int(time())
    delay = max(0, 10 - (real_now - ts1_i))
    if delay > 0:
        await asyncio.sleep(delay)

    ts2 = await r.get(f"room:{rid}:empty_since")
    if not ts2 or ts1 != ts2:
        return False

    if expected_seq is not None:
        cur_seq = int(await r.get(f"room:{rid}:gc_seq") or 0)
        if cur_seq != expected_seq:
            return False

    if int(await r.scard(f"room:{rid}:members") or 0) > 0:
        return False

    got = await r.set(f"room:{rid}:gc_lock", "1", nx=True, ex=20)
    if not got:
        return False
    try:
        raw_visitors = await r.smembers(f"room:{rid}:visitors")
        new_visitors = set()
        for u in raw_visitors:
            try:
                new_visitors.add(int(u))
            except Exception:
                continue

        async with _sessionmaker() as s:
            rm = await s.get(Room, rid)
            if rm:
                existing = set(rm.visitor_ids or [])
                rm.visitor_ids = list(sorted(existing | new_visitors))
                rm.deleted_at = datetime.now(timezone.utc)
                await s.commit()

        async def _del_scan(pattern: str, count: int = 200):
            cursor = 0
            while True:
                cursor, keys = await r.scan(cursor=cursor, match=pattern, count=count)
                if keys:
                    await r.delete(*keys)
                if cursor == 0:
                    break

        await _del_scan(f"room:{rid}:user:*:state")
        await r.delete(
            f"room:{rid}:members",
            f"room:{rid}:visitors",
            f"room:{rid}:params",
            f"room:{rid}:gc_seq",
            f"room:{rid}:empty_since",
        )
        await r.zrem("rooms:index", str(rid))
    finally:
        try:
            await r.delete(f"room:{rid}:gc_lock")
        except Exception:
            pass

    return True


async def join_room_atomic(r, rid: int, uid: int, *, retries: int = 8) -> int:
    limraw = await r.hget(f"room:{rid}:params", "user_limit")
    if not limraw:
        return -2
    try:
        lim = int(limraw)
    except Exception:
        return -2
    if lim <= 0:
        return -2

    for _ in range(retries):
        try:
            await r.watch(f"room:{rid}:members")
            already = await r.sismember(f"room:{rid}:members", uid)
            size = int(await r.scard(f"room:{rid}:members") or 0)
            if already:
                async with r.pipeline() as p:
                    p.sadd(f"room:{rid}:visitors", uid)
                    await p.execute()
                await r.unwatch()
                return size

            if size >= lim:
                await r.unwatch()
                return -1

            async with r.pipeline() as p:
                p.sadd(f"room:{rid}:members", uid)
                p.sadd(f"room:{rid}:visitors", uid)
                await p.execute()
            await r.unwatch()
            return size + 1
        except WatchError:
            continue
        finally:
            try: await r.unwatch()
            except Exception: pass

    return -1


async def leave_room_atomic(r, rid: int, uid: int, *, retries: int = 8) -> tuple[int, int]:
    for _ in range(retries):
        try:
            await r.watch(f"room:{rid}:members")
            async with r.pipeline() as p:
                p.srem(f"room:{rid}:members", uid)
                await p.execute()
            break
        except WatchError:
            continue
        finally:
            try: await r.unwatch()
            except Exception: pass

    seq = 0
    occ = int(await r.scard(f"room:{rid}:members") or 0)
    if occ == 0:
        for _ in range(retries):
            try:
                await r.watch(f"room:{rid}:members", f"room:{rid}:empty_since", f"room:{rid}:gc_seq")
                if int(await r.scard(f"room:{rid}:members") or 0) != 0:
                    await r.unwatch()
                    break
                now = int(time())
                async with r.pipeline() as p:
                    p.set(f"room:{rid}:empty_since", now, ex=86400)
                    p.incr(f"room:{rid}:gc_seq")
                    res = await p.execute()
                seq = int(res[-1])
                await r.unwatch()
                break
            except WatchError:
                continue
            finally:
                try: await r.unwatch()
                except Exception: pass

    return occ, seq

