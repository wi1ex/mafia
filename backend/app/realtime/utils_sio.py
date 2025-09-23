from __future__ import annotations
import asyncio
from time import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping
import structlog
from redis import WatchError
from sqlalchemy.ext.asyncio import async_sessionmaker
from ..core.clients import get_redis
from ..db import engine
from ..models.room import Room

__all__ = [
    "apply_state",
    "get_room_snapshot",
    "get_occupancies",
    "get_positions",
    "join_room_atomic",
    "leave_room_atomic",
    "gc_empty_room",
]

log = structlog.get_logger()

_sessionmaker = async_sessionmaker(bind=engine, expire_on_commit=False)


async def apply_state(r, rid: int, uid: int, data: Mapping[str, Any]) -> Dict[str, str]:
    m: Dict[str, str] = {}
    for k in ("mic", "cam", "speakers", "visibility"):
        if k in data:
            if isinstance(data[k], bool):
                m[k] = "1" if data[k] else "0"
            else:
                m[k] = "1" if str(data[k]).strip().lower() in {"1", "true"} else "0"
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


async def get_positions(r, rid: int) -> dict[str, int]:
    rows = await r.zrange(f"room:{rid}:order", 0, -1, withscores=True)
    out: dict[str, int] = {}
    for member, score in rows:
        m = member.decode() if isinstance(member, (bytes, bytearray)) else str(member)
        if m.isdigit():
            out[m] = int(score)
    return out


async def join_room_atomic(r, rid: int, uid: int, role: str, *, retries: int = 8) -> tuple[int, int]:
    limraw = await r.hget(f"room:{rid}:params", "user_limit")
    if not limraw:
        return -2, 0
    try:
        lim = int(limraw)
    except Exception:
        return -2, 0
    if lim <= 0:
        return -2, 0

    creator_raw = await r.hget(f"room:{rid}:params", "creator")
    try:
        creator_id = int(creator_raw or 0)
    except Exception:
        creator_id = 0
    eff_role = "host" if uid == creator_id else role

    for _ in range(retries):
        try:
            await r.watch(f"room:{rid}:members", f"room:{rid}:order")
            already = await r.sismember(f"room:{rid}:members", uid)
            size = int(await r.scard(f"room:{rid}:members") or 0)
            now = int(time())
            if already:
                pos = await r.zscore(f"room:{rid}:order", uid)
                if pos is None:
                    pos = size if size > 0 else 1
                    async with r.pipeline() as p:
                        p.zadd(f"room:{rid}:order", {uid: pos})
                        p.hset(f"room:{rid}:user:{uid}:info", mapping={"position": int(pos)})
                        await p.execute()
                existing_jd = await r.hget(f"room:{rid}:user:{uid}:info", "join_date")
                mapping: Dict[str, Any] = {"role": eff_role}
                if not existing_jd:
                    mapping["join_date"] = now
                async with r.pipeline() as p:
                    p.hset(f"room:{rid}:user:{uid}:info", mapping=mapping)
                    await p.execute()
                await r.unwatch()
                return size, int(pos)

            if size >= lim:
                await r.unwatch()
                return -1, 0

            new_pos = size + 1
            async with r.pipeline() as p:
                p.sadd(f"room:{rid}:members", uid)
                p.zadd(f"room:{rid}:order", {uid: new_pos})
                p.hset(f"room:{rid}:user:{uid}:info", mapping={"join_date": now, "position": new_pos, "role": eff_role})
                p.delete(f"room:{rid}:empty_since")
                await p.execute()
            await r.unwatch()
            return new_pos, new_pos
        except WatchError:
            continue
        finally:
            try:
                await r.unwatch()
            except Exception:
                pass

    log.warning("join.retries_exhausted", rid=rid, uid=uid, retries=retries)
    return -1, 0


async def leave_room_atomic(r, rid: int, uid: int, *, retries: int = 8) -> tuple[int, int, list[tuple[int, int]]]:
    pos = await r.zscore(f"room:{rid}:order", uid)
    try:
        pos_i = int(pos) if pos is not None else None
    except Exception:
        pos_i = None

    try:
        jd_raw = await r.hget(f"room:{rid}:user:{uid}:info", "join_date")
        jd = int(jd_raw) if jd_raw else None
        if jd:
            dt = max(0, int(time()) - jd)
            if dt:
                await r.hincrby(f"room:{rid}:visitors", str(uid), dt)
    except Exception:
        pass

    for _ in range(retries):
        try:
            await r.watch(f"room:{rid}:members", f"room:{rid}:order")
            async with r.pipeline() as p:
                p.srem(f"room:{rid}:members", uid)
                p.zrem(f"room:{rid}:order", uid)
                p.delete(f"room:{rid}:user:{uid}:info")
                await p.execute()
            break
        except WatchError:
            continue
        finally:
            try:
                await r.unwatch()
            except Exception:
                pass

    gc_seq = 0
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
                gc_seq = int(res[-1])
                await r.unwatch()
                break
            except WatchError:
                continue
            finally:
                try:
                    await r.unwatch()
                except Exception:
                    pass

    updates: list[tuple[int, int]] = []
    if occ > 0 and pos_i is not None:
        ids = await r.zrangebyscore(f"room:{rid}:order", min=pos_i + 1, max="+inf")
        if ids:
            async with r.pipeline() as p:
                for mid in ids:
                    p.zincrby(f"room:{rid}:order", -1, mid)
                new_scores = await p.execute()
            async with r.pipeline() as p2:
                for mid, sc in zip(ids, new_scores):
                    new_pos = int(sc)
                    updates.append((int(mid), new_pos))
                    p2.hset(f"room:{rid}:user:{int(mid)}:info", mapping={"position": new_pos})
                await p2.execute()

    return occ, gc_seq, updates


async def gc_empty_room(rid: int, *, expected_seq: int | None = None) -> bool:
    r = get_redis()
    ts1 = await r.get(f"room:{rid}:empty_since")
    if not ts1:
        log.debug("gc.skip.no_empty_since", rid=rid)
        return False

    ts1_i = int(ts1 if isinstance(ts1, (int, str)) else ts1.decode())
    delay = max(0, 10 - (int(time()) - ts1_i))
    if delay > 0:
        log.debug("gc.wait", rid=rid, wait_s=delay)
        await asyncio.sleep(delay)

    ts2 = await r.get(f"room:{rid}:empty_since")
    if not ts2 or ts1 != ts2:
        log.debug("gc.skip.race_or_reset", rid=rid)
        return False

    if expected_seq is not None:
        cur_seq = int(await r.get(f"room:{rid}:gc_seq") or 0)
        if cur_seq != expected_seq:
            log.debug("gc.skip.seq_mismatch", rid=rid, expected=expected_seq, current=cur_seq)
            return False

    if int(await r.scard(f"room:{rid}:members") or 0) > 0:
        log.debug("gc.skip.not_empty_anymore", rid=rid)
        return False

    got = await r.set(f"room:{rid}:gc_lock", "1", nx=True, ex=20)
    if not got:
        log.debug("gc.skip.no_lock", rid=rid)
        return False

    try:
        raw = await r.hgetall(f"room:{rid}:visitors")
        visitors_map: dict[int, int] = {}
        for k, v in (raw or {}).items():
            try:
                visitors_map[int(k)] = int(v or 0)
            except Exception:
                continue

        try:
            async with _sessionmaker() as s:
                rm = await s.get(Room, rid)
                if rm:
                    rm.visitor_ids = sorted(list({*(rm.visitor_ids or []), *visitors_map.keys()}))
                    rm.visitor_durations = {**(rm.visitor_durations or {}), **{str(k): v for k, v in visitors_map.items()}}
                    rm.deleted_at = datetime.now(timezone.utc)
                    await s.commit()
            log.info("gc.persisted_to_db", rid=rid, visitors=len(visitors_map))
        except Exception:
            log.exception("gc.db.persist_failed", rid=rid)
            raise

        async def _del_scan(pattern: str, count: int = 200):
            cursor = 0
            while True:
                cursor, keys = await r.scan(cursor=cursor, match=pattern, count=count)
                if keys:
                    await r.delete(*keys)
                if cursor == 0:
                    break

        await _del_scan(f"room:{rid}:user:*:state")
        await _del_scan(f"room:{rid}:user:*:info")
        await r.delete(
            f"room:{rid}:members",
            f"room:{rid}:order",
            f"room:{rid}:visitors",
            f"room:{rid}:params",
            f"room:{rid}:gc_seq",
            f"room:{rid}:empty_since",
            f"room:{rid}:gc_lock",
        )
        await r.zrem("rooms:index", str(rid))
        log.info("gc.done", rid=rid)
    finally:
        try:
            await r.delete(f"room:{rid}:gc_lock")
        except Exception:
            pass

    return True
