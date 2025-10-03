from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from time import time
from typing import Any, Tuple
from typing import Dict, Mapping, cast
import structlog
from jwt import ExpiredSignatureError
from redis import WatchError
from sqlalchemy.ext.asyncio import async_sessionmaker
from ..core.clients import get_redis
from ..core.logging import log_action
from ..core.security import decode_token
from ..db import engine
from ..models.room import Room

__all__ = [
    "KEYS",
    "validate_auth",
    "apply_state",
    "get_room_snapshot",
    "get_blocks_snapshot",
    "get_roles_snapshot",
    "join_room_atomic",
    "leave_room_atomic",
    "gc_empty_room",
    "update_blocks",
]

log = structlog.get_logger()

_sessionmaker = async_sessionmaker(bind=engine, expire_on_commit=False)

KEYS: tuple[str, ...] = ("mic", "cam", "speakers", "visibility")


def _norm01(v: Any) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"

    return "1" if str(v).strip().lower() in {"1", "true"} else "0"


async def validate_auth(auth: Any) -> Tuple[int, str] | None:
    token = auth.get("token") if isinstance(auth, dict) else None
    if not token:
        log.warning("sio.connect.no_token")
        return None

    try:
        p = decode_token(token)
        uid = int(p["sub"])
        sid = str(p.get("sid") or "")
        cur = await get_redis().get(f"user:{uid}:sid")
        if not cur or cur != sid:
            log.warning("sio.connect.replaced_session")
            return None

        role = str(p.get("role") or "user")
        return uid, role

    except ExpiredSignatureError:
        log.warning("sio.connect.expired_token")
        return None

    except Exception:
        log.warning("sio.connect.bad_token")
        return None


async def apply_state(r, rid: int, uid: int, data: Mapping[str, Any]) -> Dict[str, str]:
    incoming = {k: _norm01(data[k]) for k in KEYS if k in data}
    if not incoming:
        return {}

    block_vals = await r.hmget(f"room:{rid}:user:{uid}:block", *KEYS)
    blocked = {k: (v == "1") for k, v in zip(KEYS, block_vals)}
    incoming = {k: v for k, v in incoming.items() if not (blocked.get(k, False) and v == "1")}
    if not incoming:
        return {}

    cur_vals = await r.hmget(f"room:{rid}:user:{uid}:state", *KEYS)
    cur = {k: (v if v is not None else "") for k, v in zip(KEYS, cur_vals)}
    changed = {k: v for k, v in incoming.items() if cur.get(k) != v}
    if not changed:
        return {}

    await r.hset(f"room:{rid}:user:{uid}:state", mapping=changed)
    return changed


async def get_room_snapshot(r, rid: int) -> Dict[str, Dict[str, str]]:
    ids = await r.smembers(f"room:{rid}:members")
    if not ids:
        return {}

    async with r.pipeline() as p:
        for uid in ids:
            await p.hgetall(f"room:{rid}:user:{uid}:state")
        states = await p.execute()
    return {str(uid): (st or {}) for uid, st in zip(ids, states)}


async def get_blocks_snapshot(r, rid: int) -> Dict[str, Dict[str, str]]:
    ids = await r.smembers(f"room:{rid}:members")
    if not ids:
        return {}

    async with r.pipeline() as p:
        for uid in ids:
            await p.hgetall(f"room:{rid}:user:{uid}:block")
        res = await p.execute()
    out: Dict[str, Dict[str, str]] = {}
    for uid, row in zip(ids, res):
        out[str(uid)] = {k: ("1" if v == "1" else "0") for k, v in (row or {}).items() if k in KEYS}
    return out


async def get_roles_snapshot(r, rid: int) -> Dict[str, str]:
    ids = await r.smembers(f"room:{rid}:members")
    if not ids:
        return {}

    async with r.pipeline() as p:
        for uid in ids:
            await p.hget(f"room:{rid}:user:{uid}:info", "role")
        roles = await p.execute()
    out: Dict[str, str] = {}
    for uid, role in zip(ids, roles):
        if role:
            out[str(uid)] = str(role)
    return out


async def update_blocks(r, rid: int, actor_uid: int, actor_role: str, target_uid: int, changes_bool: Mapping[str, Any]) -> tuple[Dict[str, str], Dict[str, str]]:
    if not await r.sismember(f"room:{rid}:members", target_uid):
        return {}, {"__error__": "user_not_in_room"}

    role = await r.hget(f"room:{rid}:user:{target_uid}:info", "role")
    target_role = str(role or "user")
    if actor_uid == target_uid:
        return {}, {"__error__": "forbidden"}

    if actor_role not in ("admin", "host"):
        return {}, {"__error__": "forbidden"}

    if actor_role == "host" and target_role == "admin":
        return {}, {"__error__": "forbidden"}

    incoming = {k: _norm01(changes_bool[k]) for k in KEYS if k in changes_bool}
    if not incoming:
        return {}, {}

    cur_vals = await r.hmget(f"room:{rid}:user:{target_uid}:block", *KEYS)
    cur = {k: (v if v is not None else "0") for k, v in zip(KEYS, cur_vals)}
    to_apply = {k: v for k, v in incoming.items() if cur.get(k) != v}
    if not to_apply:
        return {}, {}

    await r.hset(f"room:{rid}:user:{target_uid}:block", mapping=to_apply)
    forced_off: Dict[str, str] = {}
    turn_off_keys = [k for k, v in to_apply.items() if v == "1"]
    if turn_off_keys:
        st_vals = await r.hmget(f"room:{rid}:user:{target_uid}:state", *turn_off_keys)
        for k, v in zip(turn_off_keys, st_vals):
            if (v or "0") == "1":
                forced_off[k] = "0"
        if forced_off:
            await r.hset(f"room:{rid}:user:{target_uid}:state", mapping=forced_off)
    return to_apply, forced_off


async def join_room_atomic(r, rid: int, uid: int, role: str, *, retries: int = 8) -> tuple[int, int, bool]:
    res = await r.hmget(f"room:{rid}:params", "user_limit", "creator")
    limraw, creator_raw = res
    if not limraw:
        return -2, 0, False

    try:
        lim = int(limraw)
    except Exception:
        return -2, 0, False

    if lim <= 0:
        return -2, 0, False

    try:
        creator_id = int(creator_raw or 0)
    except Exception:
        creator_id = 0
    eff_role = "host" if uid == creator_id else role
    for _ in range(retries):
        try:
            await r.watch(f"room:{rid}:members", f"room:{rid}:positions")
            already = await r.sismember(f"room:{rid}:members", uid)
            size = int(await r.scard(f"room:{rid}:members") or 0)
            now = int(time())
            if already:
                pos = await r.zscore(f"room:{rid}:positions", uid)
                if pos is None:
                    pos = size if size > 0 else 1
                    async with r.pipeline() as p:
                        await p.zadd(f"room:{rid}:positions", {uid: pos})
                        await p.execute()
                existing_jd = await r.hget(f"room:{rid}:user:{uid}:info", "join_date")
                mapping: Dict[str, Any] = {"role": eff_role}
                if not existing_jd:
                    mapping["join_date"] = now
                async with r.pipeline() as p:
                    await p.hset(f"room:{rid}:user:{uid}:info", mapping=mapping)
                    await p.execute()
                return size, int(pos), True

            if size >= lim:
                return -1, 0, False

            new_pos = size + 1
            async with r.pipeline() as p:
                await p.sadd(f"room:{rid}:members", uid)
                await p.zadd(f"room:{rid}:positions", {uid: new_pos})
                await p.hset(f"room:{rid}:user:{uid}:info", mapping={"join_date": now, "role": eff_role})
                await p.delete(f"room:{rid}:empty_since")
                await p.execute()
            return new_pos, new_pos, False

        except WatchError:
            continue
        finally:
            try:
                await r.unwatch()
            except Exception:
                pass
    log.warning("join.retries_exhausted", rid=rid, uid=uid, retries=retries)
    return -1, 0, False


async def leave_room_atomic(r, rid: int, uid: int, *, retries: int = 8) -> tuple[int, int, list[tuple[int, int]]]:
    pos = await r.zscore(f"room:{rid}:positions", uid)
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
            await r.watch(f"room:{rid}:members", f"room:{rid}:positions")
            async with r.pipeline() as p:
                await p.srem(f"room:{rid}:members", uid)
                await p.zrem(f"room:{rid}:positions", uid)
                await p.delete(f"room:{rid}:user:{uid}:info")
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
                    break
                now = int(time())
                async with r.pipeline() as p:
                    await p.set(f"room:{rid}:empty_since", now, ex=86400)
                    await p.incr(f"room:{rid}:gc_seq")
                    res = await p.execute()
                gc_seq = int(res[-1])
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
        ids = await r.zrangebyscore(f"room:{rid}:positions", min=pos_i + 1, max="+inf")
        if ids:
            async with r.pipeline() as p:
                for mid in ids:
                    await p.zincrby(f"room:{rid}:positions", -1, mid)
                new_scores = await p.execute()
            for mid, sc in zip(ids, new_scores):
                updates.append((int(mid), int(sc)))
    return occ, gc_seq, updates


async def gc_empty_room(rid: int, *, expected_seq: int | None = None) -> bool:
    r = get_redis()
    ts1 = await r.get(f"room:{rid}:empty_since")
    if not ts1:
        log.info("gc.skip.no_empty_since", rid=rid)
        return False

    delay = max(0, 10 - (int(time()) - int(ts1)))
    if delay > 0:
        log.info("gc.wait", rid=rid, wait_s=delay)
        await asyncio.sleep(delay)
    ts2 = await r.get(f"room:{rid}:empty_since")
    if not ts2 or ts1 != ts2:
        log.info("gc.skip.race_or_reset", rid=rid)
        return False

    if expected_seq is not None:
        cur_seq = int(await r.get(f"room:{rid}:gc_seq") or 0)
        if cur_seq != expected_seq:
            log.info("gc.skip.seq_mismatch", rid=rid, expected=expected_seq, current=cur_seq)
            return False

    if int(await r.scard(f"room:{rid}:members") or 0) > 0:
        log.info("gc.skip.not_empty_anymore", rid=rid)
        return False

    got = await r.set(f"room:{rid}:gc_lock", "1", nx=True, ex=20)
    if not got:
        log.info("gc.skip.no_lock", rid=rid)
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
                    rm_title = rm.title
                    rm_user_limit = rm.user_limit
                    rm_creator = cast(int, rm.creator)
                    rm_creator_name = cast(str, rm.creator_name)
                    unique_visitors = len(set(visitors_map.keys()))
                    if unique_visitors <= 1:
                        await s.delete(rm)
                    else:
                        rm.visitors = {**(rm.visitors or {}), **{str(k): v for k, v in visitors_map.items()}}
                        rm.deleted_at = datetime.now(timezone.utc)

                    await r.srem(f"user:{rm_creator}:rooms", str(rid))
                    await log_action(
                        s,
                        user_id=rm_creator,
                        username=rm_creator_name,
                        action="room_deleted",
                        details=f"Удаление комнаты room_id={rid} title={rm_title} user_limit={rm_user_limit} count_users={unique_visitors}",
                    )
            log.info("gc.persisted_to_db", rid=rid, visitors=len(visitors_map))
        except Exception:
            log.exception("gc.db.persist_failed", rid=rid)
            raise

        async def _del_scan(pattern: str, count: int = 200):
            cursor = 0
            while True:
                cursor, keys = await r.scan(cursor=cursor, match=pattern, count=count)
                if keys:
                    await r.unlink(*keys)
                if cursor == 0:
                    break

        await _del_scan(f"room:{rid}:user:*:info")
        await _del_scan(f"room:{rid}:user:*:state")
        await _del_scan(f"room:{rid}:user:*:block")
        await r.delete(
            f"room:{rid}:members",
            f"room:{rid}:positions",
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
