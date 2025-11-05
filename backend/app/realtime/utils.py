from __future__ import annotations
import asyncio
import structlog
from time import time
from sqlalchemy import select
from redis.exceptions import ResponseError
from jwt import ExpiredSignatureError
from datetime import datetime, timezone
from typing import Any, Tuple, Dict, Mapping, cast, Optional, List, Iterable
from ..core.db import SessionLocal
from ..models.room import Room
from ..models.user import User
from ..core.clients import get_redis
from ..core.logging import log_action
from ..core.security import decode_token

__all__ = [
    "KEYS_STATE",
    "KEYS_BLOCK",
    "KEYS_META",
    "validate_auth",
    "apply_state",
    "get_room_snapshot",
    "merge_ready_into_snapshot",
    "get_positions_map",
    "build_game_from_raw",
    "persist_join_user_info",
    "get_blocks_snapshot",
    "get_roles_snapshot",
    "get_profiles_snapshot",
    "account_screen_time",
    "join_room_atomic",
    "leave_room_atomic",
    "gc_empty_room",
    "update_blocks",
    "claim_screen",
    "release_screen",
    "get_room_brief",
    "get_rooms_brief",
]

log = structlog.get_logger()

KEYS_STATE: tuple[str, ...] = ("mic", "cam", "speakers", "visibility", )
KEYS_BLOCK: tuple[str, ...] = (*KEYS_STATE, "screen", )
KEYS_META: tuple[str, ...] = ("ready", )

JOIN_LUA = r'''
-- KEYS: params, members, positions, info, empty_since
local params       = KEYS[1]
local members      = KEYS[2]
local positions    = KEYS[3]
local info         = KEYS[4]
local empty_since  = KEYS[5]

local rid       = ARGV[1]
local uid       = tonumber(ARGV[2])
local base_role = ARGV[3]
local now       = tonumber(ARGV[4])

local lim = tonumber(redis.call('HGET', params, 'user_limit') or '0')
if not lim or lim <= 0 then return {-2,0,0,0} end

local creator = tonumber(redis.call('HGET', params, 'creator') or '0')
local eff_role = (uid == creator) and 'host' or base_role

local already = redis.call('SISMEMBER', members, uid)
local size = tonumber(redis.call('SCARD', members) or '0')

if already == 1 then
  local pos = tonumber(redis.call('ZSCORE', positions, uid) or '0')
  local existing_jd = redis.call('HGET', info, 'join_date')
  redis.call('HSET', info, 'role', eff_role)
  if not existing_jd then redis.call('HSET', info, 'join_date', now) end
  if not pos or pos == 0 then
    local new_pos = size
    redis.call('ZADD', positions, new_pos, uid)
    return {size, new_pos, 1, 0}
  end
  if pos < size then
    local after = redis.call('ZRANGEBYSCORE', positions, pos+1, '+inf', 'WITHSCORES')
    local new_pos = size
    local updates = {}
    for i=1,#after,2 do
      local mid = tonumber(after[i])
      redis.call('ZINCRBY', positions, -1, mid)
      local sc = tonumber(after[i+1]) - 1
      table.insert(updates, mid)
      table.insert(updates, sc)
    end
    redis.call('ZADD', positions, new_pos, uid)
    return {size, new_pos, 1, #updates/2, unpack(updates)}
  else
    return {size, pos, 1, 0}
  end
end

if size >= lim then return {-1,0,0,0} end

local new_pos = size + 1
redis.call('SADD', members, uid)
redis.call('ZADD', positions, new_pos, uid)
redis.call('HSET', info, 'join_date', now, 'role', eff_role)
redis.call('DEL', empty_since)
return {new_pos, new_pos, 0, 0}
'''

LEAVE_LUA = r'''
-- KEYS: members, positions, info, empty_since, gc_seq, visitors
local members      = KEYS[1]
local positions    = KEYS[2]
local info         = KEYS[3]
local empty_since  = KEYS[4]
local gc_seq       = KEYS[5]
local visitors     = KEYS[6]

local uid = tonumber(ARGV[1])
local now = tonumber(ARGV[2])

local pos = tonumber(redis.call('ZSCORE', positions, uid) or '0')
local jd  = tonumber(redis.call('HGET', info, 'join_date') or '0')
if jd and jd > 0 then
  local dt = now - jd
  if dt > 0 then redis.call('HINCRBY', visitors, tostring(uid), dt) end
end

redis.call('SREM', members, uid)
redis.call('ZREM', positions, uid)
redis.call('DEL', info)

local occ = tonumber(redis.call('SCARD', members) or '0')
if occ == 0 then
  redis.call('SET', empty_since, now, 'EX', 2592000)
  local seq = tonumber(redis.call('INCR', gc_seq))
  return {occ, seq, 0}
end

if not pos or pos == 0 then return {occ, 0, 0} end

local ids = redis.call('ZRANGEBYSCORE', positions, pos+1, '+inf')
local updates = {}
for i=1,#ids do
  local mid = tonumber(ids[i])
  local sc  = tonumber(redis.call('ZINCRBY', positions, -1, mid))
  table.insert(updates, mid)
  table.insert(updates, sc)
end
return {occ, 0, #updates/2, unpack(updates)}
'''

_join_sha = None
_leave_sha = None


async def _ensure_scripts(r):
    global _join_sha, _leave_sha
    if _join_sha is None:
        _join_sha = await r.script_load(JOIN_LUA)
    if _leave_sha is None:
        _leave_sha = await r.script_load(LEAVE_LUA)


def _norm01(v: Any) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"

    return "1" if str(v).strip().lower() in {"1", "true"} else "0"


async def validate_auth(auth: Any) -> Tuple[int, str, str, Optional[str]] | None:
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
        async with SessionLocal() as s:
            row = await s.execute(select(User.username, User.avatar_name).where(User.id == uid))
            rec = row.first()
            username, avatar_name = (cast(Optional[str], rec[0]), cast(Optional[str], rec[1])) if rec else (None, None)
        return uid, role, username, avatar_name

    except ExpiredSignatureError:
        log.warning("sio.connect.expired_token")
        return None

    except Exception:
        log.warning("sio.connect.bad_token")
        return None


async def apply_state(r, rid: int, uid: int, data: Mapping[str, Any]) -> Dict[str, str]:
    incoming_state = {k: _norm01(data[k]) for k in KEYS_STATE if k in data}
    incoming_meta = {k: _norm01(data[k]) for k in KEYS_META if k in data}
    if not (incoming_state or incoming_meta):
        return {}

    changed: Dict[str, str] = {}
    if incoming_state:
        block_vals = await r.hmget(f"room:{rid}:user:{uid}:block", *KEYS_BLOCK)
        blocked = {k: (v == "1") for k, v in zip(KEYS_BLOCK, block_vals)}
        incoming_state = {k: v for k, v in incoming_state.items() if not (blocked.get(k, False) and v == "1")}
        if incoming_state:
            cur_vals = await r.hmget(f"room:{rid}:user:{uid}:state", *KEYS_STATE)
            cur = {k: (v if v is not None else "") for k, v in zip(KEYS_STATE, cur_vals)}
            upd = {k: v for k, v in incoming_state.items() if cur.get(k) != v}
            if upd:
                await r.hset(f"room:{rid}:user:{uid}:state", mapping=upd)
                changed.update(upd)

    if incoming_meta:
        cur_vals = await r.hmget(f"room:{rid}:user:{uid}:meta", *KEYS_META)
        cur_m = {k: (v if v is not None else "") for k, v in zip(KEYS_META, cur_vals)}
        upd_m = {k: v for k, v in incoming_meta.items() if cur_m.get(k) != v}
        if upd_m:
            await r.hset(f"room:{rid}:user:{uid}:meta", mapping=upd_m)
            changed.update(upd_m)

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


async def get_ready_snapshot(r, rid: int) -> Dict[str, Dict[str, str]]:
    ids = await r.smembers(f"room:{rid}:members")
    if not ids:
        return {}

    async with r.pipeline() as p:
        for uid in ids:
            await p.hgetall(f"room:{rid}:user:{uid}:meta")
        metas = await p.execute()

    out: Dict[str, Dict[str, str]] = {}
    for uid, row in zip(ids, metas):
        if row and "ready" in row:
            out[str(uid)] = {"ready": "1" if str(row.get("ready") or "0") == "1" else "0"}

    return out


async def merge_ready_into_snapshot(r, rid: int, snapshot: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    ready_snap = await get_ready_snapshot(r, rid)
    for k, v in ready_snap.items():
        ss = snapshot.get(k) or {}
        snapshot[k] = {**ss, **v}

    return snapshot


async def get_positions_map(r, rid: int) -> Dict[str, int]:
    pairs = await r.zrange(f"room:{rid}:positions", 0, -1, withscores=True)
    return {str(int(m)): int(s) for m, s in pairs}


def build_game_from_raw(raw_game: Mapping[str, Any]) -> Dict[str, Any]:
    def b1(v: Any, default_true: bool = True) -> str:
        return "1" if str((v if v is not None else ("1" if default_true else "0"))).strip() in ("1", "true", "True") else "0"

    return {
        "mode": str(raw_game.get("mode") or "normal"),
        "format": str(raw_game.get("format") or "hosted"),
        "spectators_limit": int(raw_game.get("spectators_limit") or 0),
        "vote_at_zero": b1(raw_game.get("vote_at_zero"), True),
        "vote_three": b1(raw_game.get("vote_three"), True),
        "speech30_at_3_fouls": b1(raw_game.get("speech30_at_3_fouls"), True),
        "extra30_at_2_fouls": b1(raw_game.get("extra30_at_2_fouls"), True),
    }


async def persist_join_user_info(r, rid: int, uid: int, username: Optional[str], avatar_name: Optional[str]) -> None:
    mp: Dict[str, str] = {}
    if isinstance(username, str) and username.strip():
        mp["username"] = username.strip()
    if isinstance(avatar_name, str) and avatar_name.strip():
        mp["avatar_name"] = avatar_name.strip()
    if mp:
        try:
            await r.hset(f"room:{rid}:user:{uid}:info", mapping=mp)
        except Exception:
            log.warning("join.persist_info.failed", rid=rid, uid=uid)
    try:
        await r.hset(f"room:{rid}:user:{uid}:meta", mapping={"ready": "0"})
    except Exception:
        log.warning("sio.join.ready_reset_failed", rid=rid, uid=uid)


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
        out[str(uid)] = {k: ("1" if v == "1" else "0") for k, v in (row or {}).items() if k in KEYS_BLOCK}
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


async def get_profiles_snapshot(r, rid: int) -> dict[str, dict[str, str | None]]:
    ids = await r.smembers(f"room:{rid}:members")
    if not ids:
        return {}

    async with r.pipeline() as p:
        for uid in ids:
            await p.hmget(f"room:{rid}:user:{uid}:info", "username", "avatar_name")
        rows = await p.execute()

    out: dict[str, dict[str, str | None]] = {}
    need_db: list[int] = []
    for uid, (un, av) in zip(ids, rows):
        uid_s = str(uid)
        out[uid_s] = {"username": str(un) if un else None, "avatar_name": str(av) if av else None}
        if av is None or un is None:
            need_db.append(int(uid))

    if need_db:
        async with SessionLocal() as s:
            res = await s.execute(select(User.id, User.username, User.avatar_name).where(User.id.in_(need_db)))
            for uid_i, un_db, av_db in res.all():
                cur = out[str(uid_i)]
                if cur["avatar_name"] is None:
                    cur["avatar_name"] = av_db
                if cur["username"] is None:
                    cur["username"] = un_db
    return out


async def update_blocks(r, rid: int, actor_uid: int, actor_role: str, target_uid: int, changes_bool: Mapping[str, Any]) -> tuple[Dict[str, str], Dict[str, str]]:
    if not await r.sismember(f"room:{rid}:members", str(target_uid)):
        return {}, {"__error__": "user_not_in_room"}

    role = await r.hget(f"room:{rid}:user:{target_uid}:info", "role")
    target_role = str(role or "user")
    if actor_uid == target_uid:
        return {}, {"__error__": "forbidden"}

    if actor_role not in ("admin", "host"):
        return {}, {"__error__": "forbidden"}

    if actor_role == "host" and target_role == "admin":
        return {}, {"__error__": "forbidden"}

    if actor_role == target_role:
        return {}, {"__error__": "forbidden"}

    incoming = {k: _norm01(changes_bool[k]) for k in KEYS_BLOCK if k in changes_bool}
    if not incoming:
        return {}, {}

    cur_vals = await r.hmget(f"room:{rid}:user:{target_uid}:block", *KEYS_BLOCK)
    cur = {k: (v if v is not None else "0") for k, v in zip(KEYS_BLOCK, cur_vals)}
    to_apply = {k: v for k, v in incoming.items() if cur.get(k) != v}
    if not to_apply:
        return {}, {}

    await r.hset(f"room:{rid}:user:{target_uid}:block", mapping=to_apply)
    forced_off: Dict[str, str] = {}
    turn_off_keys = [k for k, v in to_apply.items() if v == "1" and k in KEYS_STATE]
    if turn_off_keys:
        st_vals = await r.hmget(f"room:{rid}:user:{target_uid}:state", *turn_off_keys)
        for k, v in zip(turn_off_keys, st_vals):
            if (v or "0") == "1":
                forced_off[k] = "0"
        if forced_off:
            await r.hset(f"room:{rid}:user:{target_uid}:state", mapping=forced_off)
    return to_apply, forced_off


async def claim_screen(r, rid: int, uid: int) -> tuple[bool, int]:
    cur = await r.get(f"room:{rid}:screen_owner")
    if cur and int(cur) != uid:
        return False, int(cur)

    ok = await r.set(f"room:{rid}:screen_owner", str(uid), nx=True)
    if ok:
        return True, uid

    cur2 = await r.get(f"room:{rid}:screen_owner")
    return (int(cur2 or 0) == uid), (int(cur2) if cur2 else 0)


async def release_screen(r, rid: int, uid: int) -> bool:
    cur = await r.get(f"room:{rid}:screen_owner")
    if cur and int(cur) == uid:
        await r.delete(f"room:{rid}:screen_owner")
        return True

    return False


async def account_screen_time(r, rid: int, uid: int) -> None:
    started = await r.get(f"room:{rid}:screen_started_at")
    if not started:
        return
    try:
        dt = int(time()) - int(started)
    except Exception:
        dt = 0
    if dt > 0:
        await r.hincrby(f"room:{rid}:screen_time", str(uid), dt)
    await r.delete(f"room:{rid}:screen_started_at")


async def get_room_brief(r, rid: int) -> Optional[dict]:
    fields = ("id", "title", "user_limit", "creator", "creator_name", "created_at", "privacy")
    _id, title, user_limit, creator, creator_name, created_at, privacy = await r.hmget(f"room:{rid}:params", *fields)
    if not (_id and title and user_limit and creator and creator_name and created_at):
        return None

    creator_id = int(creator)
    creator_avatar_name: Optional[str] = None
    occ = int(await r.scard(f"room:{rid}:members") or 0)
    try:
        async with SessionLocal() as s:
            u = await s.get(User, creator_id)
            if u:
                creator_avatar_name = cast(Optional[str], u.avatar_name)
    except Exception:
        creator_avatar_name = None

    return {
        "id": int(_id),
        "title": str(title),
        "user_limit": int(user_limit),
        "creator": creator_id,
        "creator_name": str(creator_name),
        "created_at": str(created_at),
        "privacy": str(privacy or "open"),
        "occupancy": occ,
        "creator_avatar_name": creator_avatar_name,
    }


async def get_rooms_brief(r, ids: Iterable[int]) -> List[dict]:
    tasks = [get_room_brief(r, int(rid)) for rid in ids]
    res = await asyncio.gather(*tasks, return_exceptions=False)
    return [x for x in res if x]


async def join_room_atomic(r, rid: int, uid: int, role: str):
    await _ensure_scripts(r)
    now = int(time())
    args = (
        5,
        f"room:{rid}:params",
        f"room:{rid}:members",
        f"room:{rid}:positions",
        f"room:{rid}:user:{uid}:info",
        f"room:{rid}:empty_since",
        str(rid), str(uid), role, str(now),
    )

    global _join_sha
    try:
        res = await r.evalsha(_join_sha, *args)
    except ResponseError as e:
        if "NOSCRIPT" in str(e):
            _join_sha = await r.script_load(JOIN_LUA)
            res = await r.evalsha(_join_sha, *args)
        else:
            log.exception("join.lua_error", rid=rid, uid=uid)
            raise

    occ = int(res[0])
    pos = int(res[1])
    already = bool(int(res[2]))
    k = int(res[3])
    tail = list(map(int, res[4:4+2*k]))
    updates = [(tail[i], tail[i+1]) for i in range(0, 2*k, 2)]
    return occ, pos, already, updates


async def leave_room_atomic(r, rid: int, uid: int):
    await _ensure_scripts(r)
    now = int(time())
    args = (
        6,
        f"room:{rid}:members",
        f"room:{rid}:positions",
        f"room:{rid}:user:{uid}:info",
        f"room:{rid}:empty_since",
        f"room:{rid}:gc_seq",
        f"room:{rid}:visitors",
        str(uid), str(now),
    )

    global _leave_sha
    try:
        res = await r.evalsha(_leave_sha, *args)
    except ResponseError as e:
        if "NOSCRIPT" in str(e):
            _leave_sha = await r.script_load(LEAVE_LUA)
            res = await r.evalsha(_leave_sha, *args)
        else:
            log.exception("leave.lua_error", rid=rid, uid=uid)
            raise

    occ = int(res[0])
    gc_seq = int(res[1])
    k = int(res[2])
    tail = list(map(int, res[3:3+2*k]))
    updates = [(tail[i], tail[i+1]) for i in range(0, 2*k, 2)]
    return occ, gc_seq, updates


async def gc_empty_room(rid: int, *, expected_seq: int | None = None) -> bool:
    r = get_redis()
    ts1 = await r.get(f"room:{rid}:empty_since")
    if not ts1:
        log.warning("gc.skip.no_empty_since", rid=rid)
        return False

    delay = max(0, 10 - (int(time()) - int(ts1)))
    if delay > 0:
        await asyncio.sleep(delay)
    ts2 = await r.get(f"room:{rid}:empty_since")
    if not ts2 or ts1 != ts2:
        log.warning("gc.skip.race_or_reset", rid=rid)
        return False

    if expected_seq is not None:
        cur_seq = int(await r.get(f"room:{rid}:gc_seq") or 0)
        if cur_seq != expected_seq:
            log.warning("gc.skip.seq_mismatch", rid=rid, expected=expected_seq, current=cur_seq)
            return False

    if int(await r.scard(f"room:{rid}:members") or 0) > 0:
        log.warning("gc.skip.not_empty_anymore", rid=rid)
        return False

    got = await r.set(f"room:{rid}:gc_lock", "1", nx=True, ex=20)
    if not got:
        log.warning("gc.skip.no_lock", rid=rid)
        return False

    try:
        raw = await r.hgetall(f"room:{rid}:visitors")
        visitors_map: dict[int, int] = {}
        for k, v in (raw or {}).items():
            try:
                visitors_map[int(k)] = int(v or 0)
            except Exception:
                continue

        owner = await r.get(f"room:{rid}:screen_owner")
        started = await r.get(f"room:{rid}:screen_started_at")
        if owner and started:
            try:
                dt = int(time()) - int(started)
                if dt > 0:
                    await r.hincrby(f"room:{rid}:screen_time", str(int(owner)), dt)
            except Exception as e:
                log.warning("gc.screen_time.flush_failed", rid=rid, err=type(e).__name__)

        raw_scr = await r.hgetall(f"room:{rid}:screen_time")
        screen_map_sec: dict[int, int] = {}
        for k, v in (raw_scr or {}).items():
            try:
                screen_map_sec[int(k)] = int(v or 0)
            except Exception:
                continue

        try:
            async with SessionLocal() as s:
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
                        rm.screen_time = {**(rm.screen_time or {}), **{str(uid): max(0, sec) for uid, sec in screen_map_sec.items()}}
                        rm.deleted_at = datetime.now(timezone.utc)

                    await r.srem(f"user:{rm_creator}:rooms", str(rid))
                    await log_action(
                        s,
                        user_id=rm_creator,
                        username=rm_creator_name,
                        action="room_deleted",
                        details=f"Удаление комнаты room_id={rid} title={rm_title} user_limit={rm_user_limit} count_users={unique_visitors}",
                    )
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
        await _del_scan(f"room:{rid}:user:*:meta")
        await _del_scan(f"room:{rid}:user:*:block")
        await _del_scan(f"room:{rid}:user:*:epoch")
        await r.delete(
            f"room:{rid}:members",
            f"room:{rid}:positions",
            f"room:{rid}:visitors",
            f"room:{rid}:params",
            f"room:{rid}:game",
            f"room:{rid}:gc_seq",
            f"room:{rid}:empty_since",
            f"room:{rid}:gc_lock",
            f"room:{rid}:allow",
            f"room:{rid}:pending",
            f"room:{rid}:screen_time",
            f"room:{rid}:screen_owner",
            f"room:{rid}:screen_started_at",
        )
        await r.zrem("rooms:index", str(rid))
    finally:
        try:
            await r.delete(f"room:{rid}:gc_lock")
        except Exception as e:
            log.warning("gc.lock.release_failed", rid=rid, err=type(e).__name__)

    return True
