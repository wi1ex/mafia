from __future__ import annotations
import asyncio
from random import shuffle
import structlog
from time import time
from sqlalchemy import select
from redis.exceptions import ResponseError
from jwt import ExpiredSignatureError
from datetime import datetime, timezone
from typing import Any, Tuple, Dict, Mapping, cast, Optional, List, Iterable
from .sio import sio
from ..core.db import SessionLocal
from ..core.settings import settings
from ..models.room import Room
from ..models.user import User
from ..core.clients import get_redis
from ..core.logging import log_action
from ..security.auth_tokens import decode_token

__all__ = [
    "KEYS_STATE",
    "KEYS_BLOCK",
    "validate_auth",
    "apply_state",
    "get_room_snapshot",
    "merge_ready_into_snapshot",
    "set_ready",
    "get_positions_map",
    "build_game_from_raw",
    "persist_join_user_info",
    "get_blocks_snapshot",
    "get_roles_snapshot",
    "get_profiles_snapshot",
    "join_room_atomic",
    "leave_room_atomic",
    "gc_empty_room",
    "claim_screen",
    "get_rooms_brief",
    "init_roles_deck",
    "assign_role_for_user",
    "advance_roles_turn",
    "emit_rooms_occupancy_safe",
    "get_game_runtime_and_roles_view",
    "get_nominees_in_order",
    "get_alive_and_voted_ids",
    "can_act_on_user",
    "stop_screen_for_user",
    "emit_state_changed_filtered",
    "compute_day_opening_and_closing",
    "get_alive_players_in_seat_order",
    "schedule_foul_block",
    "emit_game_fouls",
    "day_speech_timeout_job",
    "apply_blocks_and_emit",
    "finish_day_speech",
]

log = structlog.get_logger()

_join_sha: str | None = None
_leave_sha: str | None = None

KEYS_STATE: tuple[str, ...] = ("mic", "cam", "speakers", "visibility", "mirror")
KEYS_BLOCK: tuple[str, ...] = (*KEYS_STATE, "screen")

JOIN_LUA = r"""
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
if not lim or lim <= 0 then return {-3,0,0,0} end

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
"""

LEAVE_LUA = r"""
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
"""


async def ensure_scripts(r):
    global _join_sha, _leave_sha
    if _join_sha is None:
        _join_sha = await r.script_load(JOIN_LUA)
    if _leave_sha is None:
        _leave_sha = await r.script_load(LEAVE_LUA)


def norm01(v: Any) -> str:
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
    incoming_state = {k: norm01(data[k]) for k in KEYS_STATE if k in data}
    if not incoming_state:
        return {}

    changed: Dict[str, str] = {}
    block_vals = await r.hmget(f"room:{rid}:user:{uid}:block", *KEYS_BLOCK)
    blocked = {k: (v == "1") for k, v in zip(KEYS_BLOCK, block_vals)}
    incoming_state = {k: v for k, v in incoming_state.items() if not (blocked.get(k, False) and v == "1")}
    if not incoming_state:
        return {}

    cur_vals = await r.hmget(f"room:{rid}:user:{uid}:state", *KEYS_STATE)
    cur = {k: (v if v is not None else "") for k, v in zip(KEYS_STATE, cur_vals)}
    upd = {k: v for k, v in incoming_state.items() if cur.get(k) != v}
    if upd:
        await r.hset(f"room:{rid}:user:{uid}:state", mapping=upd)
        changed.update(upd)

    return changed


async def set_ready(r, rid: int, uid: int, v: Any) -> Optional[str]:
    if norm01(v) == "1":
        added = await r.sadd(f"room:{rid}:ready", str(uid))
        return "1" if int(added or 0) > 0 else None

    removed = await r.srem(f"room:{rid}:ready", str(uid))
    return "0" if int(removed or 0) > 0 else None


async def get_room_snapshot(r, rid: int) -> Dict[str, Dict[str, str]]:
    ids = await r.smembers(f"room:{rid}:members")
    if not ids:
        return {}

    async with r.pipeline() as p:
        for uid in ids:
            await p.hgetall(f"room:{rid}:user:{uid}:state")
        states = await p.execute()
    return {str(uid): (st or {}) for uid, st in zip(ids, states)}


async def merge_ready_into_snapshot(r, rid: int, snapshot: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    ready_ids = await r.smembers(f"room:{rid}:ready")
    ready_snap = {str(uid): {"ready": "1"} for uid in ready_ids} if ready_ids else {}
    for k, v in ready_snap.items():
        ss = snapshot.get(k) or {}
        snapshot[k] = {**ss, **v}
    return snapshot


async def get_positions_map(r, rid: int) -> Dict[str, int]:
    pairs = await r.zrange(f"room:{rid}:positions", 0, -1, withscores=True)
    return {str(int(m)): int(s) for m, s in pairs}


def build_game_from_raw(raw_game: Mapping[str, Any]) -> Dict[str, Any]:
    # def b1(v: Any, default_true: bool = True) -> str:
    #     default = "1" if default_true else "0"
    #     return "1" if str((v if v is not None else default)).strip() in ("1", "true", "True") else "0"

    return {
        "mode": str(raw_game.get("mode") or "normal"),
        "format": str(raw_game.get("format") or "hosted"),
        "spectators_limit": int(raw_game.get("spectators_limit") or 0),
        # "vote_at_zero": b1(raw_game.get("vote_at_zero"), True),
        # "vote_three": b1(raw_game.get("vote_three"), True),
        # "speech30_at_3_fouls": b1(raw_game.get("speech30_at_3_fouls"), True),
        # "extra30_at_2_fouls": b1(raw_game.get("extra30_at_2_fouls"), True),
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


async def get_blocks_snapshot(r, rid: int) -> Dict[str, Dict[str, str]]:
    ids = await r.smembers(f"room:{rid}:members")
    if not ids:
        return {}

    async with r.pipeline() as p:
        for uid in ids:
            await p.hmget(f"room:{rid}:user:{uid}:block", *KEYS_BLOCK)
        rows = await p.execute()

    out: Dict[str, Dict[str, str]] = {}
    for uid, vals in zip(ids, rows):
        out[str(uid)] = {k: ("1" if (v == "1") else "0") for k, v in zip(KEYS_BLOCK, (vals or []))}
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
            db_rows = res.all()

        async with r.pipeline() as p:
            for uid_i, un_db, av_db in db_rows:
                key = str(uid_i)
                cur = out.get(key) or {"username": None, "avatar_name": None}
                if cur["username"] is None and un_db is not None:
                    cur["username"] = un_db
                if cur["avatar_name"] is None and av_db is not None:
                    cur["avatar_name"] = av_db
                out[key] = cur

                mp: dict[str, str] = {}
                if cur["username"] is not None:
                    mp["username"] = str(cur["username"])
                if cur["avatar_name"] is not None:
                    mp["avatar_name"] = str(cur["avatar_name"])
                if mp:
                    await p.hset(f"room:{rid}:user:{uid_i}:info", mapping=mp)
            await p.execute()

    return out


async def update_blocks(r, rid: int, actor_uid: int, actor_role: str, target_uid: int, changes_bool: Mapping[str, Any]) -> tuple[Dict[str, str], Dict[str, str]]:
    role = await r.hget(f"room:{rid}:user:{target_uid}:info", "role")
    target_role = str(role or "user")
    if actor_uid == target_uid:
        return {}, {"__error__": "forbidden"}

    if actor_role != "head":
        if not can_act_on_user(actor_role, target_role):
            return {}, {"__error__": "forbidden"}

    incoming = {k: norm01(changes_bool[k]) for k in KEYS_BLOCK if k in changes_bool}
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


async def apply_blocks_and_emit(r, rid: int, *, actor_uid: int, actor_role: str, target_uid: int, changes_bool: Mapping[str, Any], phase_override: str | None = None) -> tuple[Dict[str, str], Dict[str, str]]:
    applied, forced_off = await update_blocks(r, rid, actor_uid, actor_role, target_uid, changes_bool)
    if "__error__" in forced_off:
        return applied, forced_off

    if forced_off:
        await emit_state_changed_filtered(r, rid, target_uid, forced_off, phase_override=phase_override)
    if applied:
        row = await r.hgetall(f"room:{rid}:user:{target_uid}:block")
        full = {k: ("1" if (row or {}).get(k) == "1" else "0") for k in KEYS_BLOCK}
        await emit_moderation_filtered(r, rid, target_uid, full, actor_uid, actor_role, phase_override=phase_override)

    return applied, forced_off


async def claim_screen(r, rid: int, uid: int) -> tuple[bool, int]:
    cur = await r.get(f"room:{rid}:screen_owner")
    if cur and int(cur) != uid:
        return False, int(cur)

    ok = await r.set(f"room:{rid}:screen_owner", str(uid), nx=True)
    if ok:
        return True, uid

    cur2 = await r.get(f"room:{rid}:screen_owner")
    return (int(cur2 or 0) == uid), (int(cur2) if cur2 else 0)


async def account_screen_time(r, rid: int, uid: int) -> None:
    started = await r.get(f"room:{rid}:screen_started_at")
    if not started:
        return

    dt = int(time()) - int(started)
    if dt > 0:
        dt = min(dt, 4*3600)
        await r.hincrby(f"room:{rid}:screen_time", str(uid), dt)
    await r.delete(f"room:{rid}:screen_started_at")


async def init_roles_deck(r, rid: int) -> None:
    roles = list(settings.ROLE_DECK)
    shuffle(roles)
    mapping = {str(i + 1): roles[i] for i in range(len(roles))}
    now_ts = int(time())
    async with r.pipeline() as p:
        await p.delete(
            f"room:{rid}:roles_cards",
            f"room:{rid}:roles_taken",
            f"room:{rid}:game_roles",
        )
        await p.hset(f"room:{rid}:roles_cards", mapping=mapping)
        await p.hset(
            f"room:{rid}:game_state",
            mapping={
                "roles_turn_uid": "0",
                "roles_turn_started": str(now_ts),
                "roles_turn_seq": "0",
                "roles_done": "0",
            },
        )
        await p.execute()


async def get_players_in_seat_order(r, rid: int) -> list[int]:
    raw_seats = await r.hgetall(f"room:{rid}:game_seats")
    players: list[tuple[int, int]] = []
    for uid_s, seat_s in (raw_seats or {}).items():
        try:
            uid = int(uid_s)
            seat = int(seat_s)
        except Exception:
            continue
        if seat and seat != 11:
            players.append((seat, uid))
    players.sort(key=lambda x: x[0])
    return [uid for _, uid in players]


async def get_alive_players_in_seat_order(r, rid: int) -> list[int]:
    order = await get_players_in_seat_order(r, rid)
    alive_raw = await r.smembers(f"room:{rid}:game_alive")
    alive: set[int] = set()
    for v in (alive_raw or []):
        try:
            alive.add(int(v))
        except Exception:
            continue

    return [uid for uid in order if uid in alive]


async def compute_day_opening_and_closing(r, rid: int, last_opening_uid: int | None) -> tuple[int, int, list[int]]:
    alive_order = await get_alive_players_in_seat_order(r, rid)
    if not alive_order:
        return 0, 0, []

    opening: int
    if last_opening_uid and last_opening_uid in alive_order:
        idx = alive_order.index(last_opening_uid)
        opening = alive_order[(idx + 1) % len(alive_order)]
    else:
        opening = alive_order[0]

    if len(alive_order) == 1:
        closing = opening
    else:
        idx_open = alive_order.index(opening)
        closing = alive_order[idx_open - 1] if idx_open > 0 else alive_order[-1]

    return opening, closing, alive_order


async def schedule_foul_block(rid: int, target_uid: int, head_uid: int, duration: int | None = None) -> None:
    try:
        sec = int(duration if duration is not None else settings.PLAYER_FOUL_SECONDS)
    except Exception:
        sec = 3

    if sec <= 0:
        sec = 3

    await asyncio.sleep(max(0, sec))
    r = get_redis()
    try:
        _, forced_off = await apply_blocks_and_emit(r, rid, actor_uid=head_uid, actor_role="head", target_uid=target_uid, changes_bool={"mic": True})
    except Exception:
        log.exception("game_foul.reblock_failed", rid=rid, head=head_uid, target=target_uid)
        return

    if "__error__" in forced_off:
        return


async def finish_day_speech(r, rid: int, raw_gstate: Mapping[str, Any], speaker_uid: int) -> dict[str, Any]:
    try:
        head_uid = int(raw_gstate.get("head") or 0)
    except Exception:
        head_uid = 0

    if head_uid and speaker_uid != head_uid:
        try:
            await apply_blocks_and_emit(r, rid, actor_uid=head_uid, actor_role="head", target_uid=speaker_uid, changes_bool={"mic": True})
        except Exception:
            log.exception("day_speech.finish.block_failed", rid=rid, head=head_uid, target=speaker_uid)

    try:
        opening_uid = int(raw_gstate.get("day_opening_uid") or 0)
    except Exception:
        opening_uid = 0
    try:
        closing_uid = int(raw_gstate.get("day_closing_uid") or 0)
    except Exception:
        closing_uid = 0

    day_speeches_done = False
    mapping: dict[str, str] = {
        "day_speech_started": "0",
        "day_speech_duration": "0",
    }
    if closing_uid and speaker_uid == closing_uid:
        mapping["day_last_opening_uid"] = str(opening_uid or 0)
        mapping["day_speeches_done"] = "1"
        day_speeches_done = True

    async with r.pipeline() as p:
        await p.hset(f"room:{rid}:game_state", mapping=mapping)
        await p.execute()

    payload: dict[str, Any] = {
        "room_id": rid,
        "speaker_uid": speaker_uid,
        "opening_uid": opening_uid,
        "closing_uid": closing_uid,
        "deadline": 0,
    }
    if day_speeches_done:
        payload["speeches_done"] = True

    return payload


async def emit_game_fouls(r, rid: int) -> None:
    try:
        raw = await r.hgetall(f"room:{rid}:game_fouls")
    except Exception:
        log.exception("game_fouls.load_failed", rid=rid)
        return

    fouls: dict[str, int] = {}
    for uid_s, cnt_s in (raw or {}).items():
        try:
            cnt = int(cnt_s or 0)
        except Exception:
            continue
        if cnt > 0:
            fouls[str(uid_s)] = cnt

    await sio.emit("game_fouls",
                   {"room_id": rid,
                    "fouls": fouls},
                   room=f"room:{rid}",
                   namespace="/room")


async def assign_role_for_user(r, rid: int, uid: int, *, card_index: int | None) -> tuple[bool, str | None, str | None]:
    existing = await r.hget(f"room:{rid}:game_roles", str(uid))
    if existing:
        return False, None, "already_has_role"

    cards = await r.hgetall(f"room:{rid}:roles_cards")
    if not cards:
        return False, None, "no_deck"

    taken = await r.hgetall(f"room:{rid}:roles_taken")
    taken_idx = {int(i) for i in (taken or {}).keys()}

    idx: int
    if card_index is not None:
        idx = int(card_index)
        if idx < 1 or idx > len(cards):
            return False, None, "bad_card"

        if idx in taken_idx:
            return False, None, "card_taken"

    else:
        free = [i for i in range(1, len(cards) + 1) if i not in taken_idx]
        if not free:
            return False, None, "no_free_cards"

        idx = free[0]

    role = cards.get(str(idx))
    if not role:
        return False, None, "bad_card"

    now_ts = int(time())
    async with r.pipeline() as p:
        await p.hset(f"room:{rid}:roles_taken", str(idx), str(uid))
        await p.hset(f"room:{rid}:game_roles", str(uid), role)
        await p.hset(
            f"room:{rid}:game_state",
            mapping={
                "roles_last_pick_user": str(uid),
                "roles_last_pick_at": str(now_ts),
            },
        )
        await p.execute()

    return True, str(role), None


async def roles_timeout_job(rid: int, seq: int, deadline: int) -> None:
    delay = max(0, deadline - int(time()))
    if delay > 0:
        await asyncio.sleep(delay + 0.05)

    r = get_redis()
    raw_state = await r.hgetall(f"room:{rid}:game_state")
    phase = str(raw_state.get("phase") or "idle")
    if phase != "roles_pick":
        return

    try:
        cur_seq = int(raw_state.get("roles_turn_seq") or 0)
    except Exception:
        return

    if cur_seq != seq:
        return

    await advance_roles_turn(r, rid, auto=True)


async def advance_roles_turn(r, rid: int, *, auto: bool) -> None:
    raw_state = await r.hgetall(f"room:{rid}:game_state")
    phase = str(raw_state.get("phase") or "idle")
    if phase != "roles_pick":
        return

    players = await get_players_in_seat_order(r, rid)
    if not players:
        return

    raw_roles = await r.hgetall(f"room:{rid}:game_roles")
    assigned = {int(k) for k in (raw_roles or {}).keys()}
    remaining = [uid for uid in players if uid not in assigned]

    if not remaining:
        await r.hset(f"room:{rid}:game_state", "roles_done", "1")

        roles_map: dict[int, str] = {}
        for uid_s, role_s in (raw_roles or {}).items():
            try:
                uid_i = int(uid_s)
            except Exception:
                continue
            if role_s is None:
                continue
            roles_map[uid_i] = str(role_s)

        try:
            head_uid = int(raw_state.get("head") or 0)
        except Exception:
            head_uid = 0

        if head_uid:
            await sio.emit("game_roles_reveal",
                           {"room_id": rid,
                            "roles": {str(uid): role for uid, role in roles_map.items()}},
                           room=f"user:{head_uid}",
                           namespace="/room")

        mafia_ids = [uid for uid, role in roles_map.items() if role == "mafia"]
        don_ids = [uid for uid, role in roles_map.items() if role == "don"]
        mafia_view = {str(uid): role for uid, role in roles_map.items() if role in ("mafia", "don")}
        don_view = {str(uid): role for uid, role in roles_map.items() if role == "mafia"}
        for uid in mafia_ids:
            await sio.emit("game_roles_reveal",
                           {"room_id": rid,
                            "roles": mafia_view},
                           room=f"user:{uid}",
                           namespace="/room")

        for uid in don_ids:
            await sio.emit("game_roles_reveal",
                           {"room_id": rid,
                            "roles": don_view},
                           room=f"user:{uid}",
                           namespace="/room")

        return

    now_ts = int(time())
    try:
        cur_uid = int(raw_state.get("roles_turn_uid") or 0)
    except Exception:
        cur_uid = 0
    try:
        started_at = int(raw_state.get("roles_turn_started") or 0)
    except Exception:
        started_at = now_ts

    if cur_uid not in remaining:
        cur_uid = remaining[0]
        started_at = now_ts

    if auto and now_ts - started_at >= settings.ROLE_PICK_SECONDS:
        ok, role, _ = await assign_role_for_user(r, rid, cur_uid, card_index=None)
        if ok and role:
            card_idx: int | None = None
            try:
                taken = await r.hgetall(f"room:{rid}:roles_taken")
                for i, u_s in (taken or {}).items():
                    try:
                        if int(u_s) == cur_uid:
                            card_idx = int(i)
                            break
                    except Exception:
                        continue
            except Exception:
                card_idx = None

            payload: dict[str, Any] = {"room_id": rid, "user_id": cur_uid, "role": role}
            if card_idx is not None:
                payload["card"] = card_idx

            await sio.emit("game_role_assigned",
                           payload,
                           room=f"user:{cur_uid}",
                           namespace="/room")

            await sio.emit("game_roles_picked",
                           {"room_id": rid,
                            "user_id": cur_uid},
                           room=f"room:{rid}",
                           namespace="/room")
            await advance_roles_turn(r, rid, auto=False)
            return

    seq = int(raw_state.get("roles_turn_seq") or 0) + 1
    deadline_ts = started_at + settings.ROLE_PICK_SECONDS
    remaining_sec = max(deadline_ts - int(time()), 0)

    async with r.pipeline() as p:
        await p.hset(
            f"room:{rid}:game_state",
            mapping={
                "roles_turn_uid": str(cur_uid),
                "roles_turn_started": str(started_at),
                "roles_turn_seq": str(seq),
            },
        )
        await p.execute()

    raw_taken = await r.hgetall(f"room:{rid}:roles_taken")
    taken_indexes = [int(i) for i in (raw_taken or {}).keys()]
    await sio.emit("game_roles_turn",
                   {"room_id": rid,
                    "user_id": cur_uid,
                    "deadline": remaining_sec,
                    "picked": list(assigned),
                    "order": players,
                    "taken_cards": taken_indexes},
                   room=f"room:{rid}",
                   namespace="/room")

    asyncio.create_task(roles_timeout_job(rid, seq, deadline_ts))


async def day_speech_timeout_job(rid: int, expected_started: int, expected_uid: int, duration: int) -> None:
    try:
        delay = int(duration)
    except Exception:
        delay = 0
    if delay <= 0:
        return

    await asyncio.sleep(max(0, delay))

    r = get_redis()
    try:
        raw_state = await r.hgetall(f"room:{rid}:game_state")
    except Exception:
        log.exception("day_speech_timeout.load_state_failed", rid=rid)
        return

    phase = str(raw_state.get("phase") or "idle")
    if phase != "day":
        return

    try:
        cur_started = int(raw_state.get("day_speech_started") or 0)
        cur_duration = int(raw_state.get("day_speech_duration") or 0)
        cur_uid = int(raw_state.get("day_current_uid") or 0)
        head_uid = int(raw_state.get("head") or 0)
    except Exception:
        return

    if not head_uid or cur_uid != expected_uid or cur_started != expected_started or cur_duration != duration:
        return

    try:
        payload = await finish_day_speech(r, rid, raw_state, expected_uid)
    except Exception:
        log.exception("day_speech_timeout.finish_failed", rid=rid, uid=expected_uid)
        return

    try:
        await sio.emit("game_day_speech",
                       payload,
                       room=f"room:{rid}",
                       namespace="/room")
    except Exception:
        log.exception("day_speech_timeout.emit_failed", rid=rid, uid=expected_uid)


async def get_rooms_brief(r, ids: Iterable[int]) -> List[dict]:
    ids_list = [int(x) for x in ids]
    if not ids_list:
        return []

    fields = ("id", "title", "user_limit", "creator", "creator_name", "creator_avatar_name", "created_at", "privacy")
    async with r.pipeline() as p:
        for rid in ids_list:
            await p.hmget(f"room:{rid}:params", *fields)
            await p.scard(f"room:{rid}:members")
            await p.hget(f"room:{rid}:game_state", "phase")
            await p.scard(f"room:{rid}:game_alive")
            await p.scard(f"room:{rid}:game_players")
        raw = await p.execute()

    briefs: List[dict] = []
    need_db: set[int] = set()

    for i in range(0, len(raw), 5):
        vals = raw[i]
        occ_members = int(raw[i + 1] or 0)
        phase_raw = raw[i + 2]
        alive_cnt = int(raw[i + 3] or 0)
        players_total = int(raw[i + 4] or 0)

        if not vals:
            continue

        _id, title, user_limit, creator, creator_name, creator_avatar_name, created_at, privacy = vals
        if not (_id and title and user_limit and creator and creator_name and created_at):
            continue

        creator_id = int(creator)
        avatar = creator_avatar_name if creator_avatar_name is not None else None
        if avatar is None:
            need_db.add(creator_id)

        phase = str(phase_raw or "idle")
        in_game = phase != "idle"
        occupancy = alive_cnt if in_game else occ_members
        eff_limit = players_total if in_game and players_total > 0 else int(user_limit)

        briefs.append({
            "id": int(_id),
            "title": str(title),
            "user_limit": eff_limit,
            "creator": creator_id,
            "creator_name": str(creator_name),
            "creator_avatar_name": avatar,
            "created_at": str(created_at),
            "privacy": str(privacy or "open"),
            "occupancy": occupancy,
            "in_game": in_game,
            "game_phase": phase,
        })

    if need_db:
        try:
            async with SessionLocal() as s:
                res = await s.execute(select(User.id, User.avatar_name).where(User.id.in_(need_db)))
                avatar_by_uid = {int(uid): cast(Optional[str], av) for uid, av in res.all()}
        except Exception:
            log.exception("rooms.brief.db_error")
            avatar_by_uid = {}

        for b in briefs:
            if b["creator_avatar_name"] is None:
                b["creator_avatar_name"] = avatar_by_uid.get(b["creator"])

    return briefs


async def join_room_atomic(r, rid: int, uid: int, role: str):
    await ensure_scripts(r)
    now_ts = int(time())
    args = (
        5,
        f"room:{rid}:params",
        f"room:{rid}:members",
        f"room:{rid}:positions",
        f"room:{rid}:user:{uid}:info",
        f"room:{rid}:empty_since",
        str(rid),
        str(uid),
        role,
        str(now_ts),
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
    tail = list(map(int, res[4: 4 + 2*k]))
    updates = [(tail[i], tail[i + 1]) for i in range(0, 2*k, 2)]
    return occ, pos, already, updates


async def leave_room_atomic(r, rid: int, uid: int):
    await ensure_scripts(r)
    now_ts = int(time())
    args = (
        6,
        f"room:{rid}:members",
        f"room:{rid}:positions",
        f"room:{rid}:user:{uid}:info",
        f"room:{rid}:empty_since",
        f"room:{rid}:gc_seq",
        f"room:{rid}:visitors",
        str(uid),
        str(now_ts),
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
    tail = list(map(int, res[3: 3 + 2*k]))
    updates = [(tail[i], tail[i + 1]) for i in range(0, 2*k, 2)]
    return occ, gc_seq, updates


async def emit_rooms_occupancy_safe(r, rid: int, occ: int) -> None:
    try:
        phase = str(await r.hget(f"room:{rid}:game_state", "phase") or "idle")
    except Exception:
        phase = "idle"

    if phase != "idle":
        try:
            alive_occ = int(await r.scard(f"room:{rid}:game_alive") or 0)
        except Exception:
            alive_occ = occ
        occ_to_send = alive_occ
    else:
        occ_to_send = occ

    await sio.emit("rooms_occupancy",
                   {"id": rid,
                    "occupancy": occ_to_send},
                   namespace="/rooms")


async def get_game_runtime_and_roles_view(r, rid: int, uid: int) -> tuple[dict[str, Any], dict[str, str], Optional[str]]:
    raw_gstate = await r.hgetall(f"room:{rid}:game_state")
    raw_seats = await r.hgetall(f"room:{rid}:game_seats")
    players_set = await r.smembers(f"room:{rid}:game_players")
    alive_set = await r.smembers(f"room:{rid}:game_alive")
    raw_roles = await r.hgetall(f"room:{rid}:game_roles")
    phase = str(raw_gstate.get("phase") or "idle")

    seats_map: dict[str, int] = {}
    for k, v in (raw_seats or {}).items():
        try:
            seats_map[str(int(k))] = int(v)
        except Exception:
            continue

    game_runtime: dict[str, Any] = {
        "phase": phase,
        "min_ready": settings.GAME_MIN_READY_PLAYERS,
        "seats": seats_map,
        "players": [int(x) for x in (players_set or [])],
        "alive": [int(x) for x in (alive_set or [])],
    }

    if phase == "idle":
        return game_runtime, {}, None

    if phase == "roles_pick":
        try:
            roles_turn_uid = int(raw_gstate.get("roles_turn_uid") or 0)
        except Exception:
            roles_turn_uid = 0
        try:
            roles_turn_started = int(raw_gstate.get("roles_turn_started") or 0)
        except Exception:
            roles_turn_started = 0

        if roles_turn_uid and roles_turn_started:
            now_ts = int(time())
            remaining = max(roles_turn_started + settings.ROLE_PICK_SECONDS - now_ts, 0)
            raw_taken = await r.hgetall(f"room:{rid}:roles_taken")

            assigned_ids: list[int] = []
            for k in (raw_roles or {}).keys():
                try:
                    assigned_ids.append(int(k))
                except Exception:
                    continue

            taken_cards: list[int] = []
            for idx_s in (raw_taken or {}).keys():
                try:
                    taken_cards.append(int(idx_s))
                except Exception:
                    continue

            order_ids = await get_players_in_seat_order(r, rid)

            game_runtime["roles_pick"] = {
                "turn_uid": roles_turn_uid,
                "deadline": remaining,
                "picked": assigned_ids,
                "order": order_ids,
                "taken_cards": taken_cards,
            }

    if phase == "mafia_talk_start":
        try:
            mafia_started = int(raw_gstate.get("mafia_talk_started") or 0)
        except Exception:
            mafia_started = 0
        try:
            mafia_duration = int(raw_gstate.get("mafia_talk_duration") or settings.MAFIA_TALK_SECONDS)
        except Exception:
            mafia_duration = settings.MAFIA_TALK_SECONDS

        if mafia_started and mafia_duration > 0:
            now_ts = int(time())
            remaining = max(mafia_started + mafia_duration - now_ts, 0)
            game_runtime["mafia_talk_start"] = {"deadline": remaining}

    if phase == "day":
        try:
            day_number = int(raw_gstate.get("day_number") or 0)
        except Exception:
            day_number = 0
        try:
            day_opening_uid = int(raw_gstate.get("day_opening_uid") or 0)
        except Exception:
            day_opening_uid = 0
        try:
            day_closing_uid = int(raw_gstate.get("day_closing_uid") or 0)
        except Exception:
            day_closing_uid = 0
        try:
            day_current_uid = int(raw_gstate.get("day_current_uid") or 0)
        except Exception:
            day_current_uid = 0
        try:
            speech_started = int(raw_gstate.get("day_speech_started") or 0)
        except Exception:
            speech_started = 0
        try:
            speech_duration = int(raw_gstate.get("day_speech_duration") or settings.PLAYER_TALK_SECONDS)
        except Exception:
            speech_duration = settings.PLAYER_TALK_SECONDS
        try:
            speeches_done = str(raw_gstate.get("day_speeches_done") or "0") == "1"
        except Exception:
            speeches_done = False

        remaining = 0
        if speech_started and speech_duration > 0:
            now_ts = int(time())
            remaining = max(speech_started + speech_duration - now_ts, 0)

        game_runtime["day"] = {
            "number": day_number,
            "opening_uid": day_opening_uid,
            "closing_uid": day_closing_uid,
            "current_uid": day_current_uid,
            "deadline": remaining,
            "speeches_done": speeches_done,
        }

        nominees = await get_nominees_in_order(r, rid)
        if nominees:
            game_runtime["day"]["nominees"] = nominees

    if phase == "vote":
        try:
            vote_current_uid = int(raw_gstate.get("vote_current_uid") or 0)
        except Exception:
            vote_current_uid = 0
        try:
            vote_started = int(raw_gstate.get("vote_started") or 0)
        except Exception:
            vote_started = 0
        try:
            vote_duration = int(raw_gstate.get("vote_duration") or getattr(settings, "VOTE_SECONDS", 3))
        except Exception:
            vote_duration = getattr(settings, "VOTE_SECONDS", 3)
        try:
            vote_done = str(raw_gstate.get("vote_done") or "0") == "1"
        except Exception:
            vote_done = False

        remaining = 0
        if vote_started and vote_duration > 0:
            now_ts = int(time())
            remaining = max(vote_started + vote_duration - now_ts, 0)

        nominees_order = await get_nominees_in_order(r, rid)
        game_runtime["vote"] = {
            "current_uid": vote_current_uid,
            "deadline": remaining,
            "nominees": nominees_order,
            "done": vote_done,
        }

    try:
        head_uid = int(raw_gstate.get("head") or 0)
    except Exception:
        head_uid = 0
    roles_map = {str(k): str(v) for k, v in (raw_roles or {}).items()}
    my_game_role = roles_map.get(str(uid))
    roles_done = str(raw_gstate.get("roles_done") or "0") == "1"
    game_roles_view: dict[str, str] = {}
    if roles_done:
        if head_uid and uid == head_uid:
            game_roles_view = dict(roles_map)
        elif my_game_role == "mafia":
            subset: dict[str, str] = {k: v for k, v in roles_map.items() if v in ("mafia", "don")}
            if my_game_role:
                subset[str(uid)] = my_game_role
            game_roles_view = subset
        elif my_game_role == "don":
            subset = {k: v for k, v in roles_map.items() if v == "mafia"}
            if my_game_role:
                subset[str(uid)] = my_game_role
            game_roles_view = subset
        elif my_game_role:
            game_roles_view[str(uid)] = my_game_role
    else:
        if my_game_role:
            game_roles_view[str(uid)] = my_game_role

    return game_runtime, game_roles_view, my_game_role


async def get_nominees_in_order(r, rid: int) -> list[int]:
    try:
        raw_nominees = await r.hgetall(f"room:{rid}:game_nominees")
    except Exception:
        raw_nominees = {}

    tmp: list[tuple[int, int]] = []
    for uid_s, idx_s in (raw_nominees or {}).items():
        try:
            u = int(uid_s)
            idx = int(idx_s or 0)
        except Exception:
            continue
        if idx > 0:
            tmp.append((idx, u))

    if not tmp:
        return []

    tmp.sort(key=lambda t: t[0])

    return [u for _, u in tmp]


async def get_alive_and_voted_ids(r, rid: int) -> tuple[set[int], set[int]]:
    alive_raw = await r.smembers(f"room:{rid}:game_alive")
    alive_ids: set[int] = set()
    for v in (alive_raw or []):
        try:
            alive_ids.add(int(v))
        except Exception:
            continue

    votes_raw = await r.hkeys(f"room:{rid}:game_votes")
    voted_ids: set[int] = set()
    for v in (votes_raw or []):
        try:
            voted_ids.add(int(v))
        except Exception:
            continue

    return alive_ids, voted_ids


def can_act_on_user(actor_role: str, target_role: str) -> bool:
    if actor_role not in ("admin", "host"):
        return False

    if actor_role == "host" and target_role == "admin":
        return False

    if actor_role == target_role:
        return False

    return True


async def stop_screen_for_user(r, rid: int, uid: int, *, canceled: bool = False) -> None:
    cur = await r.get(f"room:{rid}:screen_owner")
    if not cur or int(cur) != uid:
        return

    if canceled:
        await r.delete(f"room:{rid}:screen_started_at")
    else:
        await account_screen_time(r, rid, uid)

    await r.delete(f"room:{rid}:screen_owner")

    await sio.emit("screen_owner",
                   {"user_id": None},
                   room=f"room:{rid}",
                   namespace="/room")
    await sio.emit("rooms_stream",
                   {"id": rid,
                    "owner": None},
                   namespace="/rooms")


async def get_mafia_talk_viewers(r, rid: int, subject_uid: int, phase_override: str | None = None) -> tuple[bool, set[int]]:
    try:
        raw_gstate = await r.hgetall(f"room:{rid}:game_state")
    except Exception:
        return False, set()

    phase = str(phase_override or raw_gstate.get("phase") or "idle")
    if phase != "mafia_talk_start":
        return False, set()

    try:
        head_uid = int(raw_gstate.get("head") or 0)
    except Exception:
        head_uid = 0

    try:
        raw_roles = await r.hgetall(f"room:{rid}:game_roles")
    except Exception:
        raw_roles = {}

    viewers: set[int] = set()
    viewers.add(int(subject_uid))
    if head_uid:
        viewers.add(head_uid)

    for k, v in (raw_roles or {}).items():
        try:
            uid_i = int(k)
        except Exception:
            continue
        role = str(v or "")
        if role in ("mafia", "don"):
            viewers.add(uid_i)

    return True, viewers


async def emit_state_changed_filtered(r, rid: int, subject_uid: int, changed: dict[str, str], *, phase_override: str | None = None) -> None:
    payload = {"user_id": subject_uid, **changed}
    is_mafia_talk, viewers = await get_mafia_talk_viewers(r, rid, subject_uid, phase_override)

    if not is_mafia_talk:
        await sio.emit("state_changed",
                       payload,
                       room=f"room:{rid}",
                       namespace="/room")
        return

    for uid in viewers:
        await sio.emit("state_changed",
                       payload,
                       room=f"user:{uid}",
                       namespace="/room")


async def emit_moderation_filtered(r, rid: int, target_uid: int, blocks_full: dict[str, str], actor_uid: int, actor_role: str, *, phase_override: str | None = None) -> None:
    payload = {
        "user_id": target_uid,
        "blocks": blocks_full,
        "by": {"user_id": actor_uid, "role": actor_role},
    }

    is_mafia_talk, viewers = await get_mafia_talk_viewers(r, rid, target_uid, phase_override)

    if not is_mafia_talk:
        await sio.emit("moderation",
                       payload,
                       room=f"room:{rid}",
                       namespace="/room")
        return

    for uid in viewers:
        await sio.emit("moderation",
                       payload,
                       room=f"user:{uid}",
                       namespace="/room")


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
            f"room:{rid}:ready",
            f"room:{rid}:game_state",
            f"room:{rid}:game_seats",
            f"room:{rid}:game_players",
            f"room:{rid}:game_alive",
            f"room:{rid}:roles_cards",
            f"room:{rid}:roles_taken",
            f"room:{rid}:game_roles",
            f"room:{rid}:game_fouls",
            f"room:{rid}:game_short_speech_used",
            f"room:{rid}:game_nominees",
            f"room:{rid}:game_nom_speakers",
            f"room:{rid}:game_votes",
        )
        await r.zrem("rooms:index", str(rid))
    finally:
        try:
            await r.delete(f"room:{rid}:gc_lock")
        except Exception as e:
            log.warning("gc.lock.release_failed", rid=rid, err=type(e).__name__)

    return True
