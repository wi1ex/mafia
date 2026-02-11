from __future__ import annotations
import asyncio
import json
from random import shuffle, randint
import structlog
from time import time
from sqlalchemy import select, func, delete, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from redis.exceptions import ResponseError
from jwt import ExpiredSignatureError
from datetime import datetime, timezone
from typing import Any, Tuple, Dict, Mapping, cast, Optional, List, Iterable
from dataclasses import dataclass
from .sio import sio
from ..core.db import SessionLocal
from ..core.settings import settings
from ..security.parameters import get_cached_settings
from ..models.room import Room
from ..models.sanction import UserSanction
from ..models.user import User
from ..models.game import Game
from ..models.friend import FriendCloseness
from ..core.clients import get_redis
from ..core.logging import log_action
from ..security.auth_tokens import decode_token

__all__ = [
    "KEYS_STATE",
    "KEYS_BLOCK",
    "SANCTION_TIMEOUT",
    "SANCTION_BAN",
    "SANCTION_SUSPEND",
    "fetch_active_sanctions",
    "fetch_active_users_by_kind",
    "GameActionContext",
    "build_game_context",
    "validate_auth",
    "apply_state",
    "apply_bg_state_on_join",
    "apply_join_idle_defaults",
    "apply_join_phase_state",
    "extract_state_mapping",
    "get_user_state_and_block",
    "get_room_snapshot",
    "merge_ready_into_snapshot",
    "set_ready",
    "get_positions_map",
    "game_flag",
    "persist_join_user_info",
    "get_blocks_snapshot",
    "get_roles_snapshot",
    "get_profiles_snapshot",
    "join_room_atomic",
    "leave_room_atomic",
    "set_user_current_room",
    "clear_user_current_room",
    "find_user_rooms",
    "cleanup_user_from_room",
    "gc_empty_room",
    "claim_screen",
    "get_rooms_brief",
    "init_roles_deck",
    "assign_role_for_user",
    "advance_roles_turn",
    "emit_rooms_occupancy_safe",
    "emit_rooms_spectators_safe",
    "get_game_runtime_and_roles_view",
    "get_players_in_seat_order",
    "get_nominees_in_order",
    "get_alive_and_voted_ids",
    "can_act_on_user",
    "stop_screen_for_user",
    "emit_state_changed_filtered",
    "compute_day_opening_and_closing",
    "recompute_day_opening_and_closing_from_state",
    "get_alive_players_in_seat_order",
    "schedule_foul_block",
    "maybe_block_foul_on_reconnect",
    "emit_game_fouls",
    "get_farewell_wills",
    "get_farewell_wills_for",
    "get_farewell_limits",
    "compute_farewell_allowed",
    "ensure_farewell_limit",
    "log_game_action",
    "load_game_actions",
    "store_last_votes_snapshot",
    "get_last_votes_snapshot",
    "finish_vote_speech",
    "apply_blocks_and_emit",
    "finish_day_speech",
    "get_game_fouls",
    "enrich_game_runtime_with_vote",
    "emit_game_night_state",
    "night_state_broadcast_job",
    "night_stage_timeout_job",
    "compute_night_kill",
    "best_move_payload_from_state",
    "build_night_reset_mapping",
    "apply_night_start_blocks",
    "apply_day_visibility_unblock",
    "finish_day_prelude_speech",
    "emit_night_head_picks",
    "process_player_death",
    "require_ctx",
    "ensure_can_act_role",
    "get_active_fouls",
    "get_game_deaths",
    "get_player_ids",
    "block_vote_and_clear",
    "should_block_vote_on_death",
    "decide_vote_blocks_on_death",
    "get_positive_setting_int",
    "wink_spot_chance",
    "randomize_limit",
    "perform_game_end",
    "finish_game",
    "record_spectator_leave",
    "smembers_ints",
    "hkeys_ints",
    "hgetall_int_map",
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


SETTING_MAP = {
    "GAME_MIN_READY_PLAYERS": "game_min_ready_players",
    "ROLE_PICK_SECONDS": "role_pick_seconds",
    "MAFIA_TALK_SECONDS": "mafia_talk_seconds",
    "PLAYER_TALK_SECONDS": "player_talk_seconds",
    "PLAYER_TALK_SHORT_SECONDS": "player_talk_short_seconds",
    "PLAYER_FOUL_SECONDS": "player_foul_seconds",
    "NIGHT_ACTION_SECONDS": "night_action_seconds",
    "VOTE_SECONDS": "vote_seconds",
}


@dataclass
class GameActionContext:
    uid: int
    rid: int
    r: Any
    gstate: Mapping[str, str]
    phase: str
    head_uid: int


    @staticmethod
    def as_int(v: Any, default: int = 0) -> int:
        if v is None or v == "":
            return default

        try:
            return int(v)

        except Exception:
            return default


    @classmethod
    def from_raw_state(cls, *, uid: int, rid: int, r: Any, raw_state: Mapping[str, Any] | None, phase_override: str | None = None) -> "GameActionContext":
        raw = raw_state or {}
        phase = str(phase_override or raw.get("phase") or "idle")
        head_uid = cls.as_int(raw.get("head"), 0)
        return cls(uid=uid, rid=rid, r=r, gstate=raw, phase=phase, head_uid=head_uid)


    def gstr(self, key: str, default: str = "") -> str:
        raw = self.gstate.get(key)
        if raw is None:
            return default

        val = str(raw)
        return val if val else default


    def gint(self, key: str, default: int = 0) -> int:
        return self.as_int(self.gstate.get(key), default)


    def gbool(self, key: str, default: bool = False) -> bool:
        raw = self.gstate.get(key)
        if raw is None or raw == "":
            return default

        return str(raw).strip() == "1"


    def gcsv_ints(self, key: str) -> list[int]:
        raw = str(self.gstate.get(key) or "")
        out: list[int] = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                out.append(int(part))
            except Exception:
                continue
        return out


    def deadline(self, started_key: str, duration_key: str, *, default_duration: int | None = None) -> int:
        started = self.gint(started_key)
        duration = self.gint(duration_key, default_duration if default_duration is not None else 0)
        if started <= 0 or duration <= 0:
            return 0

        return max(started + duration - int(time()), 0)


    def ensure_phase(self, allowed: Iterable[str] | str, *, error: str = "bad_phase", status: int = 400):
        allowed_set = {allowed} if isinstance(allowed, str) else set(allowed or [])
        if allowed_set and self.phase not in allowed_set:
            return {"ok": False, "error": error, "status": status}

        return None


    def ensure_head(self, *, error: str = "forbidden", status: int = 403):
        if not self.head_uid or self.head_uid != self.uid:
            return {"ok": False, "error": error, "status": status}

        return None


    async def ensure_player(self, target_uid: int | None = None, *, alive_required: bool = True, error: str = "not_alive", status: int = 403):
        uid = self.uid if target_uid is None else target_uid
        is_player = await self.r.sismember(f"room:{self.rid}:game_players", str(uid))
        if not is_player:
            return {"ok": False, "error": error, "status": status}

        if alive_required:
            is_alive = await self.r.sismember(f"room:{self.rid}:game_alive", str(uid))
            if not is_alive:
                return {"ok": False, "error": error, "status": status}

        return None


class GameStateView:
    def __init__(self, ctx: GameActionContext, *, roles_map: Mapping[str, str], seats_map: Mapping[str, int]):
        self.ctx = ctx
        self.roles_map = dict(roles_map)
        self.seats_map = dict(seats_map)


    async def roles_pick(self, r, rid: int) -> dict[str, Any] | None:
        roles_turn_uid = self.ctx.gint("roles_turn_uid")
        roles_turn_started = self.ctx.gint("roles_turn_started")
        if not (roles_turn_uid and roles_turn_started):
            return None

        remaining = self.ctx.deadline(
            "roles_turn_started",
            "roles_turn_duration",
            default_duration=get_cached_settings().role_pick_seconds,
        )
        raw_taken = await r.hgetall(f"room:{rid}:roles_taken")
        assigned_ids = hash_keys_to_int_list(self.roles_map)
        taken_cards = hash_keys_to_int_list(raw_taken)
        order_ids = await get_players_in_seat_order(r, rid)
        return {
            "turn_uid": roles_turn_uid,
            "deadline": remaining,
            "picked": assigned_ids,
            "order": order_ids,
            "taken_cards": taken_cards,
        }


    def mafia_talk(self) -> dict[str, Any] | None:
        mafia_started = self.ctx.gint("mafia_talk_started")
        mafia_duration = self.ctx.gint("mafia_talk_duration", get_cached_settings().mafia_talk_seconds)
        if mafia_started and mafia_duration > 0:
            remaining = self.ctx.deadline(
                "mafia_talk_started",
                "mafia_talk_duration",
                default_duration=get_cached_settings().mafia_talk_seconds,
            )
            return {"deadline": remaining}

        return None


    async def day(self, r, rid: int, uid: int) -> dict[str, Any] | None:
        day_number = self.ctx.gint("day_number")
        day_opening_uid = self.ctx.gint("day_opening_uid")
        day_closing_uid = self.ctx.gint("day_closing_uid")
        day_current_uid = self.ctx.gint("day_current_uid")
        day_speech_started = self.ctx.gint("day_speech_started")
        day_speech_duration = self.ctx.gint("day_speech_duration")
        speech_active = day_speech_started > 0 and day_current_uid > 0
        speeches_done = self.ctx.gbool("day_speeches_done")
        remaining = self.ctx.deadline(
            "day_speech_started",
            "day_speech_duration",
            default_duration=get_cached_settings().player_talk_seconds,
        )

        day_section: dict[str, Any] = {
            "number": day_number,
            "opening_uid": day_opening_uid,
            "closing_uid": day_closing_uid,
            "current_uid": day_current_uid,
            "deadline": remaining,
            "speech_active": speech_active,
            "speeches_done": speeches_done,
            "vote_blocked": self.ctx.gbool("vote_blocked")
        }

        nk_uid = self.ctx.gint("night_kill_uid")
        ok = self.ctx.gbool("night_kill_ok")
        pre_pending = self.ctx.gbool("day_prelude_pending")
        pre_active = self.ctx.gbool("day_prelude_active")
        pre_done = self.ctx.gbool("day_prelude_done")
        day_section["night"] = {"kill_uid": nk_uid, "kill_ok": ok}

        pre_uid = self.ctx.gint("day_prelude_uid")
        if pre_uid or pre_done:
            day_section["prelude"] = {
                "uid": pre_uid,
                "pending": pre_pending,
                "active": pre_active,
                "done": pre_done,
            }
            if pre_active and pre_uid == day_current_uid:
                try:
                    limit = await ensure_farewell_limit(r, rid, pre_uid, mode="killed")
                    wills_for = await get_farewell_wills_for(r, rid, pre_uid)
                    allowed = await compute_farewell_allowed(r, rid, pre_uid, mode="killed")
                    day_section["farewell"] = {"limit": limit, "wills": wills_for, "allowed": allowed}
                except Exception:
                    log.exception("day.farewell_section.failed", rid=rid, uid=pre_uid)

        nominees = await get_nominees_in_order(r, rid)
        if nominees:
            day_section["nominees"] = nominees

        try:
            nominated_ids = list(await smembers_ints(r, f"room:{rid}:game_nom_speakers"))
        except Exception:
            nominated_ids = []

        day_section["nominated_speakers"] = nominated_ids
        if uid and day_current_uid == uid and not speeches_done and uid in nominated_ids:
            day_section["nominated_this_speech"] = True

        return day_section


    async def vote(self, r, rid: int) -> dict[str, Any] | None:
        vote_current_uid = self.ctx.gint("vote_current_uid")
        vote_started = self.ctx.gint("vote_started")
        vote_done = self.ctx.gbool("vote_done")
        vote_aborted = self.ctx.gbool("vote_aborted")
        vote_results_ready = self.ctx.gbool("vote_results_ready")
        vote_speeches_done = self.ctx.gbool("vote_speeches_done")
        vote_speech_uid = self.ctx.gint("vote_speech_uid")
        vote_speech_kind = self.ctx.gstr("vote_speech_kind")
        vote_speech_started = self.ctx.gint("vote_speech_started")
        vote_duration = self.ctx.gint("vote_duration", get_cached_settings().vote_seconds)
        vote_speech_duration = self.ctx.gint("vote_speech_duration")

        if vote_aborted or vote_results_ready:
            vote_current_uid = 0

        remaining = self.ctx.deadline(
            "vote_started",
            "vote_duration",
            default_duration=get_cached_settings().vote_seconds,
        )
        speech_remaining = self.ctx.deadline("vote_speech_started", "vote_speech_duration")

        leaders = self.ctx.gcsv_ints("vote_leaders_order")
        leader_idx = self.ctx.gint("vote_leader_idx")
        nominees_order = await get_nominees_in_order(r, rid)
        started_flag = bool(vote_started) and not (vote_done or vote_aborted or vote_results_ready)
        vote_section: dict[str, Any] = {
            "current_uid": vote_current_uid,
            "deadline": remaining,
            "nominees": nominees_order,
            "done": vote_done,
            "aborted": vote_aborted,
            "results_ready": vote_results_ready,
            "speeches_done": vote_speeches_done,
            "started": started_flag,
            "blocked": self.ctx.gbool("vote_blocked")
        }

        vote_lift_state = self.ctx.gstr("vote_lift_state")
        if vote_lift_state:
            vote_section["lift_state"] = vote_lift_state
        if leaders:
            vote_section["leaders"] = leaders
            vote_section["leader_idx"] = leader_idx
        if vote_speech_started > 0 and vote_speech_uid:
            vote_section["speech"] = {
                "speaker_uid": vote_speech_uid,
                "deadline": speech_remaining,
                "kind": vote_speech_kind,
            }
            if vote_speech_kind == "farewell":
                try:
                    limit = await ensure_farewell_limit(r, rid, vote_speech_uid, mode="voted")
                    wills_for = await get_farewell_wills_for(r, rid, vote_speech_uid)
                    allowed = await compute_farewell_allowed(r, rid, vote_speech_uid, mode="voted")
                    vote_section["farewell"] = {"limit": limit, "wills": wills_for, "allowed": allowed}
                except Exception:
                    log.exception("vote.farewell_section.failed", rid=rid, uid=vote_speech_uid)

        return vote_section


    async def night(self, r, rid: int, uid: int) -> dict[str, Any] | None:
        stage = self.ctx.gstr("night_stage", "sleep")
        deadline = 0
        if stage == "shoot":
            deadline = self.ctx.deadline("night_shoot_started", "night_shoot_duration")
        elif stage == "checks":
            deadline = self.ctx.deadline("night_check_started", "night_check_duration")

        night_section: dict[str, Any] = {"stage": stage, "deadline": deadline}
        my_role = self.roles_map.get(str(uid)) or ""
        head_uid_n = self.ctx.head_uid
        if head_uid_n and uid == head_uid_n:
            if stage in ("shoot", "shoot_done"):
                picks = await get_night_head_picks(r, rid, "shoot")
                night_section["head_picks"] = {"kind": "shoot", "picks": picks}
            elif stage in ("checks", "checks_done"):
                picks = await get_night_head_picks(r, rid, "checks")
                night_section["head_picks"] = {"kind": "checks", "picks": picks}

        if stage in ("shoot", "shoot_done") and my_role in ("mafia", "don"):
            my_t = self.ctx.as_int(await r.hget(f"room:{rid}:night_shots", str(uid)))
            if my_t:
                night_section["my_shot"] = {"target_id": my_t, "seat": seat_of(self.seats_map, my_t)}

        if stage in ("checks", "checks_done") and my_role in ("don", "sheriff"):
            my_t = self.ctx.as_int(await r.hget(f"room:{rid}:night_checks", str(uid)))
            if my_t:
                night_section["my_check"] = {"target_id": my_t, "seat": seat_of(self.seats_map, my_t)}

        if my_role in ("don", "sheriff"):
            checked_key = f"room:{rid}:game_checked:{my_role}"
            checked_ids = list(await smembers_ints(r, checked_key))

            night_section["checked"] = checked_ids
            known: dict[str, str] = {}
            for tu in checked_ids:
                tr = self.roles_map.get(str(tu)) or ""
                if my_role == "sheriff":
                    known[str(tu)] = "mafia" if tr in ("mafia", "don") else "citizen"
                else:
                    known[str(tu)] = "sheriff" if tr == "sheriff" else "citizen"

            night_section["known"] = known

        return night_section


SANCTION_TIMEOUT = "timeout"
SANCTION_BAN = "ban"
SANCTION_SUSPEND = "suspend"
async def fetch_active_sanctions(session: AsyncSession, user_id: int) -> dict[str, Optional[UserSanction]]:
    now = datetime.now(timezone.utc)
    rows = await session.execute(
        select(UserSanction)
        .where(
            UserSanction.user_id == int(user_id),
            UserSanction.revoked_at.is_(None),
            or_(UserSanction.expires_at.is_(None), UserSanction.expires_at > now),
        )
        .order_by(UserSanction.issued_at.desc(), UserSanction.id.desc())
    )
    items = rows.scalars().all()
    out = {
        SANCTION_TIMEOUT: None,
        SANCTION_BAN: None,
        SANCTION_SUSPEND: None,
    }
    for row in items:
        if row.kind in out and out[row.kind] is None:
            out[row.kind] = row

    return out


async def fetch_active_users_by_kind(session: AsyncSession, user_ids: Iterable[int], kind: str) -> set[int]:
    ids = [int(x) for x in user_ids]
    if not ids:
        return set()

    now = datetime.now(timezone.utc)
    rows = await session.execute(
        select(UserSanction.user_id)
        .where(
            UserSanction.user_id.in_(ids),
            UserSanction.kind == kind,
            UserSanction.revoked_at.is_(None),
            or_(UserSanction.expires_at.is_(None), UserSanction.expires_at > now),
        )
    )
    return {int(r[0]) for r in rows.all() if r and r[0] is not None}


def get_day_number(raw_state: Mapping[str, Any]) -> int:
    try:
        return int(raw_state.get("day_number") or 0)

    except Exception:
        return 0


async def log_game_action(r, rid: int, action: Mapping[str, Any]) -> None:
    try:
        payload = dict(action)
        if "ts" not in payload:
            payload["ts"] = int(time())
        raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        await r.rpush(f"room:{rid}:game_actions", raw)
    except Exception:
        log.exception("game_actions.log_failed", rid=rid, action=action.get("type"))


async def load_game_actions(r, rid: int) -> list[dict[str, Any]]:
    try:
        raw_items = await r.lrange(f"room:{rid}:game_actions", 0, -1)
    except Exception:
        log.exception("game_actions.load_failed", rid=rid)
        return []

    out: list[dict[str, Any]] = []
    for item in raw_items or []:
        if item is None:
            continue
        if isinstance(item, bytes):
            item = item.decode("utf-8", "ignore")
        try:
            obj = json.loads(str(item))
        except Exception:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


async def store_last_votes_snapshot(r, rid: int, votes: Mapping[int, int]) -> None:
    try:
        payload = {str(k): int(v) for k, v in votes.items() if int(k) > 0}
        raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        await r.set(f"room:{rid}:game_votes_last", raw, ex=86400)
    except Exception:
        log.exception("game_actions.last_votes_save_failed", rid=rid)


async def get_last_votes_snapshot(r, rid: int) -> dict[int, int]:
    try:
        raw = await r.get(f"room:{rid}:game_votes_last")
    except Exception:
        log.exception("game_actions.last_votes_load_failed", rid=rid)
        return {}

    if not raw:
        return {}

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "ignore")
    try:
        data = json.loads(str(raw))
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    out: dict[int, int] = {}
    for k, v in data.items():
        try:
            out[int(k)] = int(v)
        except Exception:
            continue

    return out


async def require_ctx(sid, *, namespace="/room", allowed_phases: str | Iterable[str] | None = None, require_head: bool = False):
    ctx, err = await build_game_context(sid, namespace=namespace)
    if err:
        return None, err

    if allowed_phases is not None:
        check = ctx.ensure_phase(allowed_phases)
        if check:
            return None, check

    if require_head:
        check = ctx.ensure_head()
        if check:
            return None, check

    return ctx, None


def get_positive_setting_int(attr: str, default: int) -> int:
    key = SETTING_MAP.get(attr)
    if key:
        raw = getattr(get_cached_settings(), key, None)
    else:
        raw = getattr(settings, attr, None)

    try:
        val = int(raw)
    except Exception:
        return int(default)

    return val if val > 0 else int(default)


def wink_spot_chance(default_percent: int = 25) -> float:
    try:
        percent = int(getattr(get_cached_settings(), "wink_spot_chance_percent"))
    except Exception:
        percent = int(default_percent)

    if percent < 0:
        percent = 0
    if percent > 100:
        percent = 100

    return percent / 100


def randomize_limit(limit: int) -> int:
    if limit <= 0:
        return 0

    low = limit - 1
    if low < 0:
        low = 0

    return randint(low, limit + 1)


def ensure_can_act_role(actor_role: str, target_role: str, *, error: str = "forbidden", status: int = 403):
    if not can_act_on_user(actor_role, target_role):
        return {"ok": False, "error": error, "status": status}

    return None


async def build_game_context(sid, *, namespace="/room") -> tuple[GameActionContext | None, dict | None]:
    sess = await sio.get_session(sid, namespace=namespace)
    uid = int(sess["uid"])
    rid = int(sess.get("rid") or 0)
    if not rid:
        return None, {"ok": False, "error": "no_room", "status": 400}

    r = get_redis()
    try:
        is_member = await r.sismember(f"room:{rid}:members", str(uid))
    except Exception:
        is_member = False
    if not is_member:
        try:
            is_spectator = await r.sismember(f"room:{rid}:spectators", str(uid))
        except Exception:
            is_spectator = False
        if not is_spectator:
            return None, {"ok": False, "error": "no_room", "status": 400}

    raw_gstate = await r.hgetall(f"room:{rid}:game_state") or {}
    ctx = GameActionContext.from_raw_state(uid=uid, rid=rid, r=r, raw_state=raw_gstate)
    return ctx, None


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


def game_flag(raw_game: Mapping[str, Any] | None, key: str, default: bool = True) -> bool:
    if not raw_game:
        return default

    v = raw_game.get(key)
    if v is None:
        return default

    if isinstance(v, bool):
        return v

    return str(v).strip().lower() in ("1", "true")


async def smembers_ints(r, key: str) -> set[int]:
    raw = await r.smembers(key)
    out: set[int] = set()
    for v in (raw or []):
        try:
            out.add(int(v))
        except Exception:
            continue
    return out


async def hkeys_ints(r, key: str) -> set[int]:
    raw = await r.hkeys(key)
    out: set[int] = set()
    for v in (raw or []):
        try:
            out.add(int(v))
        except Exception:
            continue
    return out


async def hgetall_int_map(r, key: str) -> dict[int, int]:
    raw = await r.hgetall(key)
    out: dict[int, int] = {}
    for k, v in (raw or {}).items():
        try:
            out[int(k)] = int(v or 0)
        except Exception:
            continue
    return out


def hash_keys_to_int_list(raw: Mapping[Any, Any] | None) -> list[int]:
    out: list[int] = []
    for k in (raw or {}).keys():
        try:
            out.append(int(k))
        except Exception:
            continue
    return out


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


def _decode_redis_value(val: Any) -> str:
    if isinstance(val, bytes):
        return val.decode("utf-8", "ignore")

    return str(val)


def extract_state_mapping(raw: Mapping[Any, Any], keys: Iterable[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in (raw or {}).items():
        ks = _decode_redis_value(k)
        if ks not in keys:
            continue
        out[ks] = _decode_redis_value(v)

    return out


async def apply_bg_state_on_join(r, rid: int, uid: int) -> tuple[dict[str, str], bool]:
    key = f"room:{rid}:user:{uid}:bg_state"
    try:
        raw_bg = await r.hgetall(key)
    except Exception:
        raw_bg = {}

    bg_states = extract_state_mapping(raw_bg, KEYS_STATE)
    had_bg_state = bool(bg_states)
    applied: dict[str, str] = {}
    if bg_states:
        applied = await apply_state(r, rid, uid, bg_states)
        if applied:
            await emit_state_changed_filtered(r, rid, uid, applied)

    if raw_bg:
        try:
            await r.delete(key)
        except Exception:
            log.warning("sio.bg_state.delete_failed", rid=rid, uid=uid)

    return applied, had_bg_state


async def apply_join_idle_defaults(r, rid: int, uid: int, *, user_state: Mapping[str, str], blocked: Mapping[str, Mapping[str, str]] | None) -> dict[str, str]:
    my_block = (blocked or {}).get(str(uid)) or {}
    speakers_blocked = str(my_block.get("speakers") or "0") == "1"
    visibility_blocked = str(my_block.get("visibility") or "0") == "1"
    auto_on: dict[str, str] = {}
    if not speakers_blocked and user_state.get("speakers") != "1":
        auto_on["speakers"] = "1"
    if not visibility_blocked and user_state.get("visibility") != "1":
        auto_on["visibility"] = "1"
    if not auto_on:
        return {}

    applied = await apply_state(r, rid, uid, auto_on)
    if applied:
        await emit_state_changed_filtered(r, rid, uid, applied)

    return applied


async def apply_join_phase_state(r, rid: int, uid: int, *, phase: str, raw_gstate: Mapping[str, Any], blocked: Mapping[str, Mapping[str, str]] | None) -> dict[str, str]:
    my_block = (blocked or {}).get(str(uid)) or {}

    def is_blocked(k: str) -> bool:
        return str(my_block.get(k) or "0") == "1"

    try:
        is_alive = bool(await r.sismember(f"room:{rid}:game_alive", str(uid)))
    except Exception:
        is_alive = False
    try:
        my_game_role_full = str((await r.hget(f"room:{rid}:game_roles", str(uid))) or "")
    except Exception:
        my_game_role_full = ""
    is_black = my_game_role_full in ("mafia", "don")

    mic_on = False
    if phase == "day":
        try:
            started = int(raw_gstate.get("day_speech_started") or 0)
            duration = int(raw_gstate.get("day_speech_duration") or 0)
            cur_uid = int(raw_gstate.get("day_current_uid") or 0)
        except Exception:
            started = 0
            duration = 0
            cur_uid = 0
        mic_on = started > 0 and cur_uid == uid
    elif phase == "vote":
        try:
            started = int(raw_gstate.get("vote_speech_started") or 0)
            duration = int(raw_gstate.get("vote_speech_duration") or 0)
            cur_uid = int(raw_gstate.get("vote_speech_uid") or 0)
        except Exception:
            started = 0
            duration = 0
            cur_uid = 0
        mic_on = started > 0 and cur_uid == uid

    cam_on = is_alive
    speakers_on = True
    visibility_on = phase in ("day", "vote") or (phase == "mafia_talk_start" and is_black)

    if is_blocked("mic"):
        mic_on = False
    if is_blocked("cam"):
        cam_on = False
    if is_blocked("speakers"):
        speakers_on = False
    if is_blocked("visibility"):
        visibility_on = False

    desired_state = {
        "mic": "1" if mic_on else "0",
        "cam": "1" if cam_on else "0",
        "speakers": "1" if speakers_on else "0",
        "visibility": "1" if visibility_on else "0",
    }
    return await apply_state(r, rid, uid, desired_state)


async def get_user_state_and_block(r, rid: int, uid: int) -> tuple[dict[str, str], dict[str, str]]:
    vals = await r.hmget(f"room:{rid}:user:{uid}:state", *KEYS_STATE)
    state = {k: ("1" if (v == "1" or v == b"1") else "0") for k, v in zip(KEYS_STATE, (vals or []))}
    block_vals = await r.hmget(f"room:{rid}:user:{uid}:block", *KEYS_BLOCK)
    blocked = {k: ("1" if (v == "1" or v == b"1") else "0") for k, v in zip(KEYS_BLOCK, (block_vals or []))}

    return state, blocked


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


async def get_profiles_snapshot(r, rid: int, *, extra_ids: Iterable[int | str] | None = None) -> dict[str, dict[str, str | None]]:
    ids = await r.smembers(f"room:{rid}:members")
    ids_set: set[str] = {str(uid) for uid in (ids or [])}
    if extra_ids:
        for uid in extra_ids:
            if uid is None:
                continue

            if isinstance(uid, (bytes, bytearray)):
                try:
                    uid = uid.decode()
                except Exception:
                    continue

            uid_s = str(uid)
            if uid_s:
                ids_set.add(uid_s)

    if not ids_set:
        return {}

    ids = list(ids_set)

    async with r.pipeline() as p:
        for uid in ids:
            await p.hmget(f"room:{rid}:user:{uid}:info", "username", "avatar_name")
        rows = await p.execute()

    out: dict[str, dict[str, str | None]] = {}
    need_db: set[int] = set()
    for uid, (un, av) in zip(ids, rows):
        uid_s = str(uid)
        out[uid_s] = {"username": str(un) if un else None, "avatar_name": str(av) if av else None}
        if av is None or un is None:
            try:
                need_db.add(int(uid_s))
            except Exception:
                continue

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
    raw_seats = await hgetall_int_map(r, f"room:{rid}:game_seats")
    players: list[tuple[int, int]] = []
    for uid, seat in (raw_seats or {}).items():
        if seat and seat != 11:
            players.append((seat, uid))
    players.sort(key=lambda x: x[0])
    return [uid for _, uid in players]


async def get_rooms_brief(r, ids: Iterable[int]) -> List[dict]:
    ids_list = [int(x) for x in ids]
    if not ids_list:
        return []

    fields = ("id", "title", "user_limit", "creator", "creator_name", "creator_avatar_name", "created_at", "privacy", "entry_closed")
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

        _id, title, user_limit, creator, creator_name, creator_avatar_name, created_at, privacy, entry_closed_raw = vals
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
        entry_closed = str(entry_closed_raw or "0") == "1"

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
            "entry_closed": entry_closed,
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


async def set_user_current_room(r, uid: int, rid: int) -> None:
    try:
        await r.set(f"user:{int(uid)}:room", str(int(rid)))
    except Exception:
        log.warning("user.room.set_failed", uid=uid, rid=rid)


async def clear_user_current_room(r, uid: int, *, rid: int | None = None) -> None:
    key = f"user:{int(uid)}:room"
    try:
        if rid is None:
            await r.delete(key)
            return

        raw = await r.get(key)
        if raw and int(raw) == int(rid):
            await r.delete(key)

    except Exception:
        log.warning("user.room.clear_failed", uid=uid, rid=rid)


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
    await clear_user_current_room(r, uid, rid=rid)
    return occ, gc_seq, updates


async def find_user_rooms(r, uid: int, *, current_rid: int, extra_rids: Iterable[int] | None = None) -> list[tuple[int, bool, bool]]:
    room_ids: list[int] = []
    seen: set[int] = set()
    try:
        raw_ids = await r.zrange("rooms:index", 0, -1)
    except Exception:
        raw_ids = []

    for raw in raw_ids or []:
        try:
            rid = int(raw)
        except Exception:
            continue
        if rid == current_rid or rid in seen:
            continue
        seen.add(rid)
        room_ids.append(rid)

    for extra in extra_rids or []:
        try:
            rid = int(extra)
        except Exception:
            continue
        if rid == current_rid or rid in seen:
            continue
        seen.add(rid)
        room_ids.append(rid)

    if not room_ids:
        return []

    try:
        async with r.pipeline() as p:
            for rid in room_ids:
                await p.sismember(f"room:{rid}:members", str(uid))
                await p.sismember(f"room:{rid}:spectators", str(uid))
            res = await p.execute()
    except Exception:
        res = None

    found: list[tuple[int, bool, bool]] = []
    if res is None:
        for rid in room_ids:
            try:
                is_member = await r.sismember(f"room:{rid}:members", str(uid))
                is_spectator = await r.sismember(f"room:{rid}:spectators", str(uid))
            except Exception:
                continue
            if is_member or is_spectator:
                found.append((rid, bool(is_member), bool(is_spectator)))
        return found

    for idx, rid in enumerate(room_ids):
        is_member = bool(res[2 * idx])
        is_spectator = bool(res[2 * idx + 1])
        if is_member or is_spectator:
            found.append((rid, is_member, is_spectator))

    return found


async def cleanup_user_from_room(r, rid: int, uid: int, *, was_member: bool, was_spectator: bool, sid: str | None, actor_username: str | None) -> None:
    if not was_member and not was_spectator:
        return

    try:
        await r.srem(f"room:{rid}:ready", str(uid))
    except Exception as err:
        log.warning("sio.join.cleanup.ready_delete_failed", rid=rid, uid=uid, err=type(err).__name__)
    try:
        await r.delete(f"room:{rid}:user:{uid}:epoch", f"room:{rid}:user:{uid}:bg_state")
    except Exception as err:
        log.warning("sio.join.cleanup.epoch_delete_failed", rid=rid, uid=uid, err=type(err).__name__)

    if was_spectator:
        try:
            await record_spectator_leave(r, rid, uid, int(time()))
        except Exception:
            log.exception("sio.join.cleanup_spectator_failed", rid=rid, uid=uid)

    if was_member:
        try:
            await stop_screen_for_user(r, rid, uid, actor_uid=uid, actor_username=actor_username)
        except Exception as err:
            log.warning("sio.join.cleanup.stop_screen_failed", rid=rid, uid=uid, err=type(err).__name__)

        gc_seq = 0
        pos_updates = []
        try:
            occ, gc_seq, pos_updates = await leave_room_atomic(r, rid, uid)
        except Exception:
            log.exception("sio.join.cleanup.leave_room_failed", rid=rid, uid=uid)
            occ = None

        if occ is not None:
            await sio.emit("member_left",
                           {"user_id": uid},
                           room=f"room:{rid}",
                           namespace="/room")
            if pos_updates:
                await sio.emit("positions",
                               {"updates": [{"user_id": u, "position": p} for u, p in pos_updates]},
                               room=f"room:{rid}",
                               namespace="/room")
            await emit_rooms_occupancy_safe(r, rid, occ)

            if occ == 0:
                try:
                    phase = str(await r.hget(f"room:{rid}:game_state", "phase") or "idle")
                except Exception:
                    phase = "idle"
                if phase == "idle":
                    async def _gc():
                        try:
                            removed = await gc_empty_room(rid, expected_seq=gc_seq)
                            if removed:
                                await sio.emit("rooms_remove",
                                               {"id": rid},
                                               namespace="/rooms")
                        except Exception:
                            log.exception("sio.join.cleanup.gc_failed", rid=rid)

                    asyncio.create_task(_gc())

    if sid:
        try:
            await sio.leave_room(sid,
                                 f"room:{rid}",
                                 namespace="/room")
        except Exception:
            log.warning("sio.join.cleanup.leave_socket_room_failed", rid=rid, uid=uid)


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


async def emit_rooms_spectators_safe(r, rid: int, count: int | None = None) -> None:
    if count is None:
        try:
            count = int(await r.scard(f"room:{rid}:spectators") or 0)
        except Exception:
            count = 0

    await sio.emit("rooms_spectators",
                   {"id": rid,
                    "spectators_count": count},
                   namespace="/rooms")


async def get_alive_players_in_seat_order(r, rid: int) -> list[int]:
    order = await get_players_in_seat_order(r, rid)
    alive = await get_effective_alive_set(r, rid, order)

    return [uid for uid in order if uid in alive]


async def get_effective_alive_set(r, rid: int, seat_order: list[int] | None = None) -> set[int]:
    try:
        alive_set = await smembers_ints(r, f"room:{rid}:game_alive")
    except Exception:
        alive_set = set()

    if seat_order is None:
        try:
            seat_order = await get_players_in_seat_order(r, rid)
        except Exception:
            seat_order = []

    if not seat_order:
        return alive_set

    try:
        deaths = await hkeys_ints(r, f"room:{rid}:game_deaths")
    except Exception:
        deaths = set()

    alive_from_deaths = set(seat_order) - deaths

    return alive_from_deaths


async def compute_day_opening_and_closing(r, rid: int, last_opening_uid: int | None, exclude: Iterable[int] | None = None) -> tuple[int, int, list[int]]:
    exclude_set: set[int] = set()
    for v in (exclude or []):
        try:
            exclude_set.add(int(v))
        except Exception:
            continue

    seat_order = await get_players_in_seat_order(r, rid)
    alive_set = await get_effective_alive_set(r, rid, seat_order)
    if exclude_set:
        alive_set.difference_update(exclude_set)
    alive_order = [uid for uid in seat_order if uid in alive_set]
    if not alive_order:
        return 0, 0, []

    opening: int | None = None
    if last_opening_uid and last_opening_uid in seat_order:
        start_idx = seat_order.index(last_opening_uid)
        total = len(seat_order)
        for step in range(1, total + 1):
            cand = seat_order[(start_idx + step) % total]
            if cand in alive_set:
                opening = cand
                break

    if opening is None:
        opening = alive_order[0]

    if len(alive_order) == 1:
        closing = opening
    else:
        idx_open = alive_order.index(opening)
        closing = alive_order[idx_open - 1] if idx_open > 0 else alive_order[-1]

    return opening, closing, alive_order


async def recompute_day_opening_and_closing_from_state(r, rid: int, raw_gstate: Mapping[str, Any]) -> tuple[int, int]:
    try:
        opening_uid = int(raw_gstate.get("day_opening_uid") or 0)
    except Exception:
        opening_uid = 0
    try:
        closing_uid = int(raw_gstate.get("day_closing_uid") or 0)
    except Exception:
        closing_uid = 0

    if not opening_uid:
        return opening_uid, closing_uid

    try:
        seat_order = await get_players_in_seat_order(r, rid)
    except Exception:
        seat_order = []
    if not seat_order:
        return opening_uid, closing_uid

    if opening_uid not in seat_order:
        try:
            last_opening_uid = int(raw_gstate.get("day_last_opening_uid") or 0)
        except Exception:
            last_opening_uid = 0
        opening_uid, closing_uid, _ = await compute_day_opening_and_closing(r, rid, last_opening_uid)
        if opening_uid and closing_uid:
            try:
                await r.hset(
                    f"room:{rid}:game_state",
                    mapping={
                        "day_opening_uid": str(opening_uid),
                        "day_closing_uid": str(closing_uid),
                    },
                )
            except Exception:
                log.exception("day_opening_closing.recompute_failed", rid=rid)
        return opening_uid, closing_uid

    try:
        alive_set = await get_effective_alive_set(r, rid, seat_order)
    except Exception:
        alive_set = set()
    if not alive_set:
        return opening_uid, closing_uid

    idx_open = seat_order.index(opening_uid)
    total = len(seat_order)
    new_closing = 0
    for step in range(1, total + 1):
        cand = seat_order[(idx_open - step) % total]
        if cand in alive_set:
            new_closing = cand
            break

    if new_closing and new_closing != closing_uid:
        try:
            await r.hset(
                f"room:{rid}:game_state",
                mapping={"day_closing_uid": str(new_closing)},
            )
        except Exception:
            log.exception("day_closing.recompute_failed", rid=rid)
        closing_uid = new_closing

    return opening_uid, closing_uid


async def get_active_fouls(r, rid: int) -> dict[int, int]:
    try:
        raw = await hgetall_int_map(r, f"room:{rid}:foul_active")
    except Exception:
        return {}

    now_ts = int(time())
    active: dict[int, int] = {}
    for uid, until_ts in (raw or {}).items():
        if until_ts > now_ts:
            active[uid] = until_ts - now_ts

    return active


async def get_player_ids(r, rid: int) -> list[int]:
    return list(await smembers_ints(r, f"room:{rid}:game_players"))


def build_night_reset_mapping(*, include_vote_meta: bool) -> dict[str, str]:
    mapping = {
        "phase": "night",
        "night_stage": "sleep",
        "night_shoot_started": "0",
        "night_shoot_duration": "0",
        "night_check_started": "0",
        "night_check_duration": "0",
        "night_kill_uid": "0",
        "night_kill_ok": "0",
        "day_prelude_uid": "0",
        "day_prelude_pending": "0",
        "day_prelude_active": "0",
        "day_prelude_done": "0",
        "best_move_uid": "0",
        "best_move_active": "0",
        "best_move_targets": "",
        "vote_blocked": "0",
    }
    if include_vote_meta:
        mapping["vote_prev_leaders"] = ""
        mapping["vote_lift_state"] = ""
    return mapping


async def apply_night_start_blocks(r, rid: int, *, head_uid: int, emit_safe: bool) -> None:
    player_ids = await get_player_ids(r, rid)
    active_fouls_map = await get_active_fouls(r, rid)
    active_foul_ids = set(active_fouls_map.keys())
    for target_uid in player_ids:
        if target_uid in active_foul_ids:
            continue
        try:
            await apply_blocks_and_emit(r, rid, actor_uid=head_uid, actor_role="head", target_uid=target_uid,
                                        changes_bool={"visibility": True, "mic": True})
        except Exception:
            log.exception("night.start.block_failed", rid=rid, head=head_uid, target=target_uid)

    async with r.pipeline() as p:
        for target_uid in player_ids:
            if target_uid in active_foul_ids:
                continue
            await p.hset(f"room:{rid}:user:{target_uid}:state", mapping={"visibility": "0", "mic": "0"})
        await p.execute()

    for target_uid in player_ids:
        if target_uid in active_foul_ids:
            continue
        if emit_safe:
            try:
                await emit_state_changed_filtered(r, rid, target_uid, {"visibility": "0", "mic": "0"}, phase_override="night")
            except Exception:
                log.exception("night.start.emit_state_failed", rid=rid, uid=target_uid)
        else:
            await emit_state_changed_filtered(r, rid, target_uid, {"visibility": "0", "mic": "0"}, phase_override="night")


async def apply_day_visibility_unblock(r, rid: int, *, head_uid: int, player_ids: list[int] | None = None) -> list[int]:
    if player_ids is None:
        player_ids = await get_player_ids(r, rid)

    for target_uid in player_ids:
        try:
            await apply_blocks_and_emit(r, rid, actor_uid=head_uid, actor_role="head", target_uid=target_uid, changes_bool={"visibility": False})
        except Exception:
            log.exception("night.day.unblock_visibility_failed", rid=rid, head=head_uid, target=target_uid)

    async with r.pipeline() as p:
        for target_uid in player_ids:
            await p.hset(f"room:{rid}:user:{target_uid}:state", mapping={"visibility": "1"})
        await p.execute()
    for target_uid in player_ids:
        await emit_state_changed_filtered(r, rid, target_uid, {"visibility": "1"})
    return player_ids


async def schedule_foul_block(rid: int, target_uid: int, head_uid: int, duration: int | None = None, *, expected_until: int | None = None) -> None:
    try:
        sec = int(duration if duration is not None else get_cached_settings().player_foul_seconds)
    except Exception:
        sec = 3

    if sec <= 0:
        sec = 3

    await asyncio.sleep(max(0, sec))

    r = get_redis()
    try:
        raw_state = await r.hgetall(f"room:{rid}:game_state")
    except Exception:
        raw_state = {}

    if not raw_state:
        return

    phase = str(raw_state.get("phase") or "")
    if phase == "idle":
        return

    if expected_until is not None:
        try:
            cur_until_raw = await r.hget(f"room:{rid}:foul_active", str(target_uid))
            cur_until = int(cur_until_raw or 0)
        except Exception:
            cur_until = 0
        if cur_until != expected_until:
            return

    keep_mic_on = False
    if raw_state:
        try:
            if phase == "day":
                cur_uid = int(raw_state.get("day_current_uid") or 0)
                started = int(raw_state.get("day_speech_started") or 0)
                duration_cur = int(raw_state.get("day_speech_duration") or 0)
                keep_mic_on = cur_uid == target_uid and started > 0
            elif phase == "vote":
                cur_uid = int(raw_state.get("vote_speech_uid") or 0)
                started = int(raw_state.get("vote_speech_started") or 0)
                duration_cur = int(raw_state.get("vote_speech_duration") or 0)
                keep_mic_on = cur_uid == target_uid and started > 0
        except Exception:
            log.exception("game_foul.check_speech_failed", rid=rid, uid=target_uid)

    if keep_mic_on:
        try:
            await r.hdel(f"room:{rid}:foul_active", str(target_uid))
        except Exception:
            log.warning("game_foul.skip_off_cleanup_failed", rid=rid, uid=target_uid)
        return

    try:
        _, forced_off = await apply_blocks_and_emit(r, rid, actor_uid=head_uid, actor_role="head", target_uid=target_uid, changes_bool={"mic": True})
    except Exception:
        log.exception("game_foul.reblock_failed", rid=rid, head=head_uid, target=target_uid)
        return

    if "__error__" in forced_off:
        return

    try:
        await r.hdel(f"room:{rid}:foul_active", str(target_uid))
    except Exception:
        log.warning("game_foul.cleanup_failed", rid=rid, uid=target_uid)


async def maybe_block_foul_on_reconnect(r, rid: int, uid: int, raw_gstate: Mapping[str, Any]) -> None:
    phase = str(raw_gstate.get("phase") or "idle")
    if phase not in ("day", "vote"):
        return

    try:
        head_uid = int(raw_gstate.get("head") or 0)
    except Exception:
        head_uid = 0
    if not head_uid or head_uid == uid:
        return

    keep_mic_on = False
    try:
        if phase == "day":
            cur_uid = int(raw_gstate.get("day_current_uid") or 0)
            started = int(raw_gstate.get("day_speech_started") or 0)
            duration_cur = int(raw_gstate.get("day_speech_duration") or 0)
            keep_mic_on = cur_uid == uid and started > 0
        elif phase == "vote":
            cur_uid = int(raw_gstate.get("vote_speech_uid") or 0)
            started = int(raw_gstate.get("vote_speech_started") or 0)
            duration_cur = int(raw_gstate.get("vote_speech_duration") or 0)
            keep_mic_on = cur_uid == uid and started > 0
    except Exception:
        log.exception("foul_reconnect.check_failed", rid=rid, uid=uid)

    if keep_mic_on:
        return

    try:
        await apply_blocks_and_emit(r, rid, actor_uid=head_uid, actor_role="head", target_uid=uid, changes_bool={"mic": True})
    except Exception:
        log.exception("foul_reconnect.block_failed", rid=rid, uid=uid, head=head_uid)


async def finish_day_speech(r, rid: int, raw_gstate: Mapping[str, Any], speaker_uid: int) -> dict[str, Any]:
    ctx = GameActionContext.from_raw_state(uid=speaker_uid, rid=rid, r=r, raw_state=raw_gstate)
    head_uid = ctx.head_uid
    if head_uid and speaker_uid != head_uid:
        try:
            await apply_blocks_and_emit(r, rid, actor_uid=head_uid, actor_role="head", target_uid=speaker_uid, changes_bool={"mic": True})
        except Exception:
            log.exception("day_speech.finish.block_failed", rid=rid, head=head_uid, target=speaker_uid)

    opening_uid, closing_uid = await recompute_day_opening_and_closing_from_state(r, rid, raw_gstate)
    day_speeches_done = False
    mapping: dict[str, str] = {
        "day_speech_started": "0",
        "day_speech_duration": "0",
    }
    if opening_uid:
        mapping["day_opening_uid"] = str(opening_uid)
    if closing_uid:
        mapping["day_closing_uid"] = str(closing_uid)
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
        "vote_blocked": ctx.gbool("vote_blocked"),
    }
    if day_speeches_done:
        payload["speeches_done"] = True

    return payload


async def get_game_fouls(r, rid: int) -> dict[str, int]:
    try:
        raw = await hgetall_int_map(r, f"room:{rid}:game_fouls")
    except Exception:
        log.exception("game_fouls.load_failed", rid=rid)
        return {}

    fouls: dict[str, int] = {}
    for uid, cnt in (raw or {}).items():
        if cnt > 0:
            fouls[str(uid)] = cnt

    return fouls


async def emit_game_fouls(r, rid: int) -> None:
    try:
        fouls = await get_game_fouls(r, rid)
    except Exception:
        log.exception("game_fouls.load_failed", rid=rid)
        return

    await sio.emit("game_fouls",
                   {"room_id": rid,
                    "fouls": fouls},
                   room=f"room:{rid}",
                   namespace="/room")


async def get_game_deaths(r, rid: int) -> dict[str, str]:
    try:
        raw = await r.hgetall(f"room:{rid}:game_deaths")
    except Exception:
        log.exception("game_deaths.load_failed", rid=rid)
        return {}

    out: dict[str, str] = {}
    for uid_s, reason in (raw or {}).items():
        if not uid_s:
            continue
        try:
            int(uid_s)
        except Exception:
            continue
        out[str(uid_s)] = str(reason or "")

    return out


async def get_farewell_wills(r, rid: int) -> dict[str, dict[str, str]]:
    try:
        raw = await r.hgetall(f"room:{rid}:game_farewell_wills")
    except Exception:
        log.exception("farewell_wills.load_failed", rid=rid)
        return {}

    out: dict[str, dict[str, str]] = {}
    for k_raw, verdict_raw in (raw or {}).items():
        if not k_raw:
            continue
        try:
            speaker_s, target_s = str(k_raw).split(":", 1)
        except Exception:
            continue
        if not speaker_s or not target_s:
            continue
        verdict = str(verdict_raw or "")
        if verdict not in ("citizen", "mafia"):
            continue
        bucket = out.get(speaker_s)
        if bucket is None:
            bucket = {}
            out[speaker_s] = bucket
        bucket[target_s] = verdict

    return out


async def get_farewell_wills_for(r, rid: int, speaker_uid: int) -> dict[str, str]:
    all_wills = await get_farewell_wills(r, rid)
    return all_wills.get(str(speaker_uid), {})


async def get_farewell_limits(r, rid: int) -> dict[str, int]:
    try:
        raw = await hgetall_int_map(r, f"room:{rid}:game_farewell_limits")
    except Exception:
        log.exception("farewell_limits.load_failed", rid=rid)
        return {}

    out: dict[str, int] = {}
    for uid, lim in (raw or {}).items():
        out[str(uid)] = lim if lim > 0 else 0

    return out


def farewell_formula(x: int) -> int:
    if x <= 0:
        return 0

    return (x // 2) + 1


async def compute_farewell_limit(r, rid: int, speaker_uid: int, *, mode: str = "killed") -> int:
    alive = await smembers_ints(r, f"room:{rid}:game_alive")
    others = len([u for u in alive if u != speaker_uid])
    if mode == "voted":
        return max(farewell_formula(others - 1), 0)

    return max(farewell_formula(others), 0)


async def compute_farewell_allowed(r, rid: int, speaker_uid: int, *, mode: str = "killed") -> bool:
    try:
        raw_game = await r.hgetall(f"room:{rid}:game")
    except Exception:
        raw_game = {}
    if not game_flag(raw_game, "farewell_wills", True):
        return False

    alive = await smembers_ints(r, f"room:{rid}:game_alive")
    others = [u for u in alive if u != speaker_uid]
    x = len(others)

    if mode == "voted":
        if not game_flag(raw_game, "break_at_zero", True):
            try:
                day_number = int(await r.hget(f"room:{rid}:game_state", "day_number") or 0)
            except Exception:
                day_number = 0

            if day_number == 1:
                try:
                    lift_state = str(await r.hget(f"room:{rid}:game_state", "vote_lift_state") or "")
                except Exception:
                    lift_state = ""

                if lift_state != "passed":
                    return False

    try:
        raw_roles = await r.hgetall(f"room:{rid}:game_roles")
    except Exception:
        raw_roles = {}

    mafia_count = 0
    speaker_role = None
    for k, role in (raw_roles or {}).items():
        try:
            uid = int(k)
        except Exception:
            continue
        if uid == speaker_uid:
            speaker_role = role
        if uid not in others:
            continue
        if str(role or "") in ("mafia", "don"):
            mafia_count += 1

    if str(speaker_role or "") in ("mafia", "don") and mafia_count == 0:
        return False

    if mode == "voted":
        return (x - 1) > 2 * mafia_count

    return x > 2 * mafia_count


async def ensure_farewell_limit(r, rid: int, speaker_uid: int, *, mode: str = "killed") -> int:
    try:
        raw_game = await r.hgetall(f"room:{rid}:game")
    except Exception:
        raw_game = {}
    if not game_flag(raw_game, "farewell_wills", True):
        return 0

    try:
        existing_raw = await r.hget(f"room:{rid}:game_farewell_limits", str(speaker_uid))
    except Exception:
        existing_raw = None
    if existing_raw is not None:
        try:
            cur = int(existing_raw or 0)
        except Exception:
            cur = 0
        if cur >= 0:
            return cur

    limit = await compute_farewell_limit(r, rid, speaker_uid, mode=mode)
    try:
        await r.hset(f"room:{rid}:game_farewell_limits", str(speaker_uid), str(limit))
    except Exception:
        log.warning("farewell_limit.save_failed", rid=rid, uid=speaker_uid)

    return limit


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

    if auto and now_ts - started_at >= get_cached_settings().role_pick_seconds:
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
    deadline_ts = started_at + get_cached_settings().role_pick_seconds
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


async def finish_vote_speech(r, rid: int, raw_gstate: Mapping[str, Any], speaker_uid: int, *, reason_override: str | None = None) -> dict[str, Any]:
    ctx = GameActionContext.from_raw_state(uid=speaker_uid, rid=rid, r=r, raw_state=raw_gstate)
    head_uid = ctx.head_uid
    if head_uid and speaker_uid != head_uid:
        try:
            await apply_blocks_and_emit(r, rid, actor_uid=head_uid, actor_role="head", target_uid=speaker_uid, changes_bool={"mic": True})
        except Exception:
            log.exception("vote_speech.finish.block_failed", rid=rid, head=head_uid, target=speaker_uid)

    kind = ctx.gstr("vote_speech_kind")
    leaders = ctx.gcsv_ints("vote_leaders_order")
    leader_idx = ctx.gint("vote_leader_idx")
    killed = False
    speeches_done = False
    if kind == "farewell":
        skip_death = False
        try:
            raw_game = await r.hgetall(f"room:{rid}:game")
        except Exception:
            raw_game = {}

        if ctx.gint("day_number") == 1 and len(leaders) == 1 and not game_flag(raw_game, "break_at_zero", True):
            skip_death = True

        if not skip_death:
            await process_player_death(r, rid, speaker_uid, head_uid=head_uid, phase_override="vote", reason=reason_override or "vote")
            killed = True

        if leaders and leader_idx >= len(leaders):
            speeches_done = True
    else:
        if leaders and leader_idx >= len(leaders):
            speeches_done = True

    async with r.pipeline() as p:
        await p.hset(
            f"room:{rid}:game_state",
            mapping={
                "vote_speech_uid": "0",
                "vote_speech_started": "0",
                "vote_speech_duration": "0",
                "vote_speech_kind": "",
                "vote_speeches_done": "1" if speeches_done else "0",
            },
        )
        await p.execute()

    payload: dict[str, Any] = {
        "room_id": rid,
        "speaker_uid": speaker_uid,
        "opening_uid": 0,
        "closing_uid": 0,
        "deadline": 0,
    }
    if killed:
        payload["killed"] = True
    if speeches_done:
        payload["speeches_done"] = True

    return payload


async def emit_game_night_state(rid: int, raw_gstate: Mapping[str, Any]) -> None:
    ctx = GameActionContext.from_raw_state(uid=0, rid=rid, r=None, raw_state=raw_gstate)
    if ctx.phase != "night":
        return

    stage = ctx.gstr("night_stage", "sleep")
    deadline = 0
    if stage == "shoot":
        deadline = ctx.deadline("night_shoot_started", "night_shoot_duration")
    elif stage == "checks":
        deadline = ctx.deadline("night_check_started", "night_check_duration")

    night_payload = {"stage": stage, "deadline": deadline}
    best_move = best_move_payload_from_state(ctx, include_empty=True)
    if best_move is not None:
        night_payload["best_move"] = best_move

    await sio.emit("game_night_state",
                   {"room_id": rid,
                    "night": night_payload},
                   room=f"room:{rid}",
                   namespace="/room")


def seat_of(seats_map: Mapping[str, Any], uid: int) -> int:
    try:
        return int(seats_map.get(str(uid)) or 0)
    except Exception:
        return 0


async def compute_night_kill(r, rid: int, *, log_action_bool: bool = True) -> tuple[int, bool]:
    raw_roles = await r.hgetall(f"room:{rid}:game_roles")
    roles_map: dict[int, str] = {}
    for k, v in (raw_roles or {}).items():
        try:
            roles_map[int(k)] = str(v or "")
        except Exception:
            continue

    alive = await smembers_ints(r, f"room:{rid}:game_alive")
    shooters = [u for u, role in roles_map.items() if role in ("mafia", "don") and u in alive]
    if not shooters:
        return 0, False

    shots_map = await hgetall_int_map(r, f"room:{rid}:night_shots")
    targets: list[int] = [shots_map.get(u, 0) for u in shooters]
    kill_uid = 0
    ok = False
    if targets and not any(t <= 0 for t in targets):
        first = targets[0]
        if not any(t != first for t in targets) and first in alive:
            kill_uid = first
            ok = True

    try:
        day_number = int(await r.hget(f"room:{rid}:game_state", "day_number") or 0)
    except Exception:
        day_number = 0

    if log_action_bool:
        await log_game_action(
            r,
            rid,
            {
                "type": "night_shoot_result",
                "day": day_number,
                "shooters": shooters,
                "shots": shots_map,
                "kill_uid": kill_uid,
                "kill_ok": ok,
            },
        )

    return kill_uid, ok


def best_move_payload_from_state(ctx: GameActionContext, *, include_empty: bool = False) -> dict[str, Any] | None:
    best_uid = ctx.gint("best_move_uid")
    active = ctx.gbool("best_move_active")
    targets = ctx.gcsv_ints("best_move_targets")
    if not include_empty and not (best_uid or active or targets):
        return None

    return {"uid": best_uid, "active": active, "targets": targets}


async def compute_best_move_eligible(r, rid: int, victim_uid: int) -> bool:
    if not victim_uid:
        return False

    try:
        day_number = int(await r.hget(f"room:{rid}:game_state", "day_number") or 0)
    except Exception:
        day_number = 0
    if day_number != 1:
        return False

    try:
        deaths_cnt = int(await r.hlen(f"room:{rid}:game_deaths") or 0)
    except Exception:
        deaths_cnt = 0
    if deaths_cnt > 1:
        return False

    try:
        alive_cnt = int(await r.scard(f"room:{rid}:game_alive") or 0)
    except Exception:
        alive_cnt = 0
    if alive_cnt < get_cached_settings().game_min_ready_players - 1:
        return False

    try:
        is_alive = await r.sismember(f"room:{rid}:game_alive", str(victim_uid))
    except Exception:
        return False

    return bool(is_alive)


async def get_night_head_picks(r, rid: int, kind: str) -> dict[str, int]:
    raw_roles = await r.hgetall(f"room:{rid}:game_roles")
    roles_map: dict[int, str] = {}
    for k, v in (raw_roles or {}).items():
        try:
            roles_map[int(k)] = str(v or "")
        except Exception:
            continue

    alive = await smembers_ints(r, f"room:{rid}:game_alive")
    seats = await r.hgetall(f"room:{rid}:game_seats")
    if kind == "shoot":
        actors = [u for u, role in roles_map.items() if role in ("mafia", "don") and u in alive]
        raw_map = await hgetall_int_map(r, f"room:{rid}:night_shots")
    else:
        actors = [u for u, role in roles_map.items() if role in ("don", "sheriff") and u in alive]
        raw_map = await hgetall_int_map(r, f"room:{rid}:night_checks")

    out: dict[str, int] = {}
    for u in actors:
        t = raw_map.get(u, 0)
        if t > 0:
            out[str(u)] = seat_of(seats, t)
    return out


async def night_state_broadcast_job(rid: int, expected_stage: str, expected_started: int, duration: int) -> None:
    try:
        duration_val = int(duration)
    except Exception:
        return

    if duration_val <= 0 or expected_started <= 0:
        return

    interval = min(1, duration_val)
    if interval <= 0:
        return

    r = get_redis()
    attempts_left = max(2, 0)
    if attempts_left <= 0:
        return

    while attempts_left > 0:
        await asyncio.sleep(interval)
        try:
            raw = await r.hgetall(f"room:{rid}:game_state")
        except Exception:
            log.exception("night_state_broadcast.load_failed", rid=rid)
            return

        ctx = GameActionContext.from_raw_state(uid=0, rid=rid, r=r, raw_state=raw)
        if ctx.phase != "night":
            return

        stage = ctx.gstr("night_stage", "sleep")
        if stage != expected_stage:
            try:
                await emit_game_night_state(rid, raw)
            except Exception:
                log.exception("night_state_broadcast.emit_failed", rid=rid)
            return

        if expected_stage == "shoot":
            cur_started = ctx.gint("night_shoot_started")
            cur_dur = ctx.gint("night_shoot_duration")
            if cur_started != expected_started or cur_dur != duration_val:
                return

            remaining = ctx.deadline("night_shoot_started", "night_shoot_duration")
        elif expected_stage == "checks":
            cur_started = ctx.gint("night_check_started")
            cur_dur = ctx.gint("night_check_duration")
            if cur_started != expected_started or cur_dur != duration_val:
                return

            remaining = ctx.deadline("night_check_started", "night_check_duration")
        else:
            return

        try:
            await emit_game_night_state(rid, raw)
        except Exception:
            log.exception("night_state_broadcast.emit_failed", rid=rid)
            return

        if remaining <= 0:
            return

        attempts_left -= 1


async def night_stage_timeout_job(rid: int, expected_stage: str, expected_started: int, duration: int, next_stage: str) -> None:
    try:
        delay = int(duration)
    except Exception:
        delay = 0
    if delay <= 0:
        return

    await asyncio.sleep(max(0, delay))
    r = get_redis()
    try:
        raw = await r.hgetall(f"room:{rid}:game_state")
    except Exception:
        return

    ctx = GameActionContext.from_raw_state(uid=0, rid=rid, r=r, raw_state=raw)
    if ctx.phase != "night":
        return

    stage = ctx.gstr("night_stage", "sleep")
    if stage != expected_stage:
        return

    if expected_stage == "shoot":
        cur_started = ctx.gint("night_shoot_started")
        cur_dur = ctx.gint("night_shoot_duration")
        if cur_started != expected_started or cur_dur != duration:
            return

        async with r.pipeline() as p:
            await p.hset(
                f"room:{rid}:game_state",
                mapping={
                    "night_stage": next_stage,
                    "night_shoot_started": "0",
                    "night_shoot_duration": "0",
                },
            )
            await p.execute()

        raw2 = dict(raw)
        raw2["night_stage"] = next_stage
        raw2["night_shoot_started"] = "0"
        raw2["night_shoot_duration"] = "0"
        await emit_game_night_state(rid, raw2)
        return

    if expected_stage == "checks":
        cur_started = ctx.gint("night_check_started")
        cur_dur = ctx.gint("night_check_duration")
        if cur_started != expected_started or cur_dur != duration:
            return

        async with r.pipeline() as p:
            await p.hset(
                f"room:{rid}:game_state",
                mapping={
                    "night_stage": next_stage,
                    "night_check_started": "0",
                    "night_check_duration": "0",
                },
            )
            await p.execute()

        raw2 = dict(raw)
        raw2["night_stage"] = next_stage
        raw2["night_check_started"] = "0"
        raw2["night_check_duration"] = "0"
        if next_stage == "checks_done":
            best_move_uid = 0
            try:
                killed_uid, ok = await compute_night_kill(r, rid, log_action_bool=False)
            except Exception:
                killed_uid, ok = 0, False
            if ok and killed_uid:
                try:
                    allowed = await compute_best_move_eligible(r, rid, killed_uid)
                except Exception:
                    allowed = False
                if allowed:
                    best_move_uid = killed_uid
            async with r.pipeline() as p:
                await p.hset(
                    f"room:{rid}:game_state",
                    mapping={
                        "best_move_uid": str(best_move_uid),
                        "best_move_active": "0",
                        "best_move_targets": "",
                    },
                )
                await p.execute()
            raw2["best_move_uid"] = str(best_move_uid)
            raw2["best_move_active"] = "0"
            raw2["best_move_targets"] = ""

        await emit_game_night_state(rid, raw2)

        return


async def emit_night_head_picks(r, rid: int, kind: str, head_uid: int) -> None:
    if not head_uid:
        return

    try:
        picks = await get_night_head_picks(r, rid, kind)
    except Exception:
        log.exception("night.head_picks.build_failed", rid=rid, kind=kind)
        return

    action = "shoot" if kind == "shoot" else "check"
    await sio.emit("game_night_head_picks",
                   {"room_id": rid,
                    "kind": kind,
                    "action": action,
                    "picks": picks},
                   room=f"user:{head_uid}",
                   namespace="/room")


async def process_player_death(r, rid: int, user_id: int, *, head_uid: int | None = None, actor_role: str = "head", phase_override: str | None = None, reason: str | None = None) -> bool:
    removed = int(await r.srem(f"room:{rid}:game_alive", str(user_id)) or 0) > 0
    if removed:
        try:
            alive_cnt = int(await r.scard(f"room:{rid}:game_alive") or 0)
        except Exception:
            alive_cnt = 0
        await sio.emit("rooms_occupancy",
                       {"id": rid,
                        "occupancy": alive_cnt},
                       namespace="/rooms")

    block_map = {"mic": "1", "cam": "1", "speakers": "0", "visibility": "0", "screen": "0"}
    await r.hset(f"room:{rid}:user:{user_id}:block", mapping=block_map)
    try:
        await emit_moderation_filtered(r, rid, user_id, block_map, head_uid if head_uid else user_id, actor_role, phase_override=phase_override)
    except Exception:
        log.exception("process_player_death.emit_moderation_failed", rid=rid, uid=user_id)

    state_map = {"mic": "0", "cam": "0", "speakers": "1", "visibility": "1"}
    await r.hset(f"room:{rid}:user:{user_id}:state", mapping=state_map)
    try:
        await emit_state_changed_filtered(r, rid, user_id, state_map, phase_override=phase_override)
    except Exception:
        log.exception("process_player_death.emit_state_failed", rid=rid, uid=user_id)

    raw_state: Mapping[str, Any] | None = None
    if reason and removed:
        try:
            await r.hset(f"room:{rid}:game_deaths", str(user_id), str(reason))
        except Exception:
            log.warning("process_player_death.reason_save_failed", rid=rid, uid=user_id)
        try:
            raw_state = await r.hgetall(f"room:{rid}:game_state")
        except Exception:
            raw_state = {}

        day_number = get_day_number(raw_state)
        if reason in ("vote", "night"):
            try:
                wills_for = await get_farewell_wills_for(r, rid, user_id)
            except Exception:
                wills_for = {}
            if wills_for:
                mode = "voted" if reason == "vote" else "killed"
                await log_game_action(
                    r,
                    rid,
                    {
                        "type": "farewell",
                        "actor_id": user_id,
                        "wills": wills_for,
                        "mode": mode,
                        "day": day_number,
                    },
                )

        action: dict[str, Any] = {
            "type": "death",
            "reason": str(reason),
            "target_id": user_id,
            "day": day_number,
        }
        if reason == "vote":
            voters: list[int] = []
            votes = await get_last_votes_snapshot(r, rid)
            if not votes:
                try:
                    raw_votes = await hgetall_int_map(r, f"room:{rid}:game_votes")
                except Exception:
                    raw_votes = {}
                for voter_i, target_i in (raw_votes or {}).items():
                    if voter_i > 0:
                        votes[voter_i] = target_i
            for voter_i, target_i in (votes or {}).items():
                if target_i == user_id:
                    voters.append(int(voter_i))
            if voters:
                action["by"] = voters
        elif reason == "night":
            shooters: list[int] = []
            try:
                raw_shots = await hgetall_int_map(r, f"room:{rid}:night_shots")
            except Exception:
                raw_shots = {}
            for shooter_i, target_i in (raw_shots or {}).items():
                if shooter_i > 0 and target_i == user_id:
                    shooters.append(shooter_i)
            if shooters:
                action["by"] = shooters
        elif reason == "foul":
            if head_uid:
                action["by"] = [head_uid]
        elif reason == "suicide":
            action["by"] = [user_id]

        await log_game_action(r, rid, action)

    if removed:
        if raw_state is None:
            try:
                raw_state = await r.hgetall(f"room:{rid}:game_state")
            except Exception:
                raw_state = {}
        if raw_state and str(raw_state.get("phase") or "") == "day":
            if str(raw_state.get("day_speeches_done") or "0") != "1":
                await recompute_day_opening_and_closing_from_state(r, rid, raw_state)

    if removed:
        try:
            await sio.emit("game_player_left",
                           {"room_id": rid,
                            "user_id": user_id,
                            "reason": reason or ""},
                           room=f"room:{rid}",
                           namespace="/room")
        except Exception:
            log.exception("process_player_death.player_left_emit_failed", rid=rid, uid=user_id)

    if head_uid and head_uid != user_id:
        try:
            await apply_blocks_and_emit(r, rid, actor_uid=head_uid, actor_role="head", target_uid=user_id, phase_override=phase_override,
                                        changes_bool={"mic": True, "cam": True, "speakers": False, "visibility": False})
        except Exception:
            log.exception("process_player_death.autoblock_failed", rid=rid, head=head_uid, target=user_id)

    if removed:
        try:
            await r.hset(f"room:{rid}:game_state", mapping={"draw_base_day": "0", "draw_base_alive": "0"})
        except Exception:
            log.warning("process_player_death.draw_reset_failed", rid=rid, uid=user_id)

        try:
            await maybe_finish_game_after_death(r, rid, head_uid=head_uid)
        except Exception:
            log.exception("process_player_death.finish_check_failed", rid=rid, uid=user_id)

    return removed


async def maybe_finish_game_after_death(r, rid: int, *, head_uid: int | None = None) -> bool:
    try:
        raw_state = await r.hgetall(f"room:{rid}:game_state")
    except Exception:
        log.exception("game_finish.load_state_failed", rid=rid)
        return False

    if not raw_state or str(raw_state.get("game_finished") or "0") == "1":
        return False

    alive_ids = await smembers_ints(r, f"room:{rid}:game_alive")
    alive_cnt = len(alive_ids)
    if alive_cnt <= 0:
        return False

    try:
        raw_roles = await r.hgetall(f"room:{rid}:game_roles")
    except Exception:
        raw_roles = {}

    black_cnt = 0
    for uid in alive_ids:
        role = str(raw_roles.get(str(uid)) or "")
        if role in ("mafia", "don"):
            black_cnt += 1

    if black_cnt == 0:
        return await finish_game(r, rid, result="red", head_uid=head_uid, reason="victory_red")

    if black_cnt * 2 >= alive_cnt:
        return await finish_game(r, rid, result="black", head_uid=head_uid, reason="victory_black")

    return False


async def finish_game(r, rid: int, *, result: str, head_uid: int | None = None, reason: str = "auto_finish") -> bool:
    if result not in ("red", "black", "draw"):
        return False

    try:
        raw_state = await r.hgetall(f"room:{rid}:game_state")
    except Exception:
        log.exception("game_finish.load_state_failed", rid=rid)
        return False

    if not raw_state:
        return False

    if str(raw_state.get("phase") or "idle") == "idle":
        return False

    if str(raw_state.get("game_finished") or "0") == "1":
        return False

    if head_uid is None:
        try:
            head_uid = int(raw_state.get("head") or 0)
        except Exception:
            head_uid = 0

    finished_ts = int(time())
    await r.hset(f"room:{rid}:game_state", mapping={"game_finished": "1", "game_result": result, "finished_at": str(finished_ts)})

    try:
        raw_roles = await r.hgetall(f"room:{rid}:game_roles")
    except Exception:
        raw_roles = {}

    roles_map = {str(k): str(v) for k, v in (raw_roles or {}).items() if v is not None}

    seats_map: dict[str, int] = {}
    try:
        raw_seats = await r.hgetall(f"room:{rid}:game_seats")
    except Exception:
        log.exception("game_finish.load_seats_failed", rid=rid)
        raw_seats = {}
    for k, v in (raw_seats or {}).items():
        try:
            uid_i = int(k)
            seat_i = int(v)
        except Exception:
            continue
        if seat_i > 0 and seat_i != 11:
            seats_map[str(uid_i)] = seat_i

    try:
        alive_ids = await smembers_ints(r, f"room:{rid}:game_alive")
    except Exception:
        log.exception("game_finish.load_alive_failed", rid=rid)
        alive_ids = set()

    black_alive_at_finish = 0
    for uid in (alive_ids or set()):
        role = roles_map.get(str(uid))
        if role in ("mafia", "don"):
            black_alive_at_finish += 1

    try:
        players_set = await r.smembers(f"room:{rid}:game_players")
    except Exception:
        log.exception("game_finish.load_players_failed", rid=rid)
        players_set = set()

    player_ids: list[int] = []
    for v in (players_set or []):
        try:
            uid_i = int(v)
        except Exception:
            continue
        if uid_i > 0:
            player_ids.append(uid_i)

    actions = await load_game_actions(r, rid)

    room_owner_id = 0
    try:
        params = await r.hgetall(f"room:{rid}:params")
        room_owner_id = int(params.get("creator") or 0)
    except Exception:
        log.exception("game_finish.load_room_params_failed", rid=rid)

    if room_owner_id <= 0:
        try:
            async with SessionLocal() as s:
                room = await s.get(Room, rid)
                if room:
                    room_owner_id = int(room.creator)
        except Exception:
            log.exception("game_finish.load_room_db_failed", rid=rid)

    phase = str(raw_state.get("phase") or "")
    skip_save = phase in ("roles_pick", "mafia_talk_start", "mafia_talk_end")
    if room_owner_id > 0 and not skip_save:
        try:
            started_ts = int(raw_state.get("started_at") or 0)
        except Exception:
            started_ts = 0
        if started_ts <= 0:
            started_ts = finished_ts
        started_at = datetime.fromtimestamp(started_ts, tz=timezone.utc)
        finished_at = datetime.fromtimestamp(finished_ts, tz=timezone.utc)

        points_map = {str(uid): 0 for uid in player_ids}
        mmr_map = {str(uid): 0 for uid in player_ids}
        try:
            async with SessionLocal() as s:
                s.add(
                    Game(
                        room_id=rid,
                        room_owner_id=room_owner_id,
                        head_id=head_uid if head_uid and head_uid > 0 else None,
                        result=result,
                        started_at=started_at,
                        finished_at=finished_at,
                        roles=roles_map,
                        seats=seats_map,
                        points=points_map,
                        mmr=mmr_map,
                        actions=actions,
                        black_alive_at_finish=black_alive_at_finish,
                    )
                )
                await bump_friend_closeness(s, player_ids)
                await s.commit()
        except Exception:
            log.exception("game_finish.save_failed", rid=rid)
    elif skip_save:
        log.info("game_finish.skip_save_early_phase", rid=rid, phase=phase, result=result)
    else:
        log.warning("game_finish.owner_missing", rid=rid)

    try:
        members_set = await r.smembers(f"room:{rid}:members")
    except Exception:
        log.exception("game_finish.load_members_failed", rid=rid)
        members_set = set()

    member_ids: set[int] = set()
    for v in (members_set or []):
        try:
            member_ids.add(int(v))
        except Exception:
            continue

    target_ids: list[int] = []
    for v in (players_set or []):
        try:
            uid_i = int(v)
        except Exception:
            continue
        if uid_i in member_ids:
            target_ids.append(uid_i)

    actor_uid = head_uid or 0
    for target_uid in target_ids:
        if actor_uid and actor_uid == target_uid:
            continue
        try:
            await apply_blocks_and_emit(r, rid, actor_uid=actor_uid, actor_role="head", target_uid=target_uid, phase_override="idle",
                                        changes_bool={"mic": False, "cam": False, "speakers": False, "visibility": False})
        except Exception:
            log.exception("game_finish.auto_unblock_failed", rid=rid, head=actor_uid, target=target_uid)

    for target_uid in target_ids:
        try:
            new_state = await apply_state(r, rid, target_uid, {"mic": True, "cam": True, "speakers": True, "visibility": True})
            if new_state:
                await emit_state_changed_filtered(r, rid, target_uid, new_state, phase_override="idle")
        except Exception:
            log.exception("game_finish.auto_state_enable_failed", rid=rid, target=target_uid)

    await sio.emit("game_finished",
                   {"room_id": rid,
                    "result": result,
                    "roles": roles_map},
                   room=f"room:{rid}",
                   namespace="/room")

    asyncio.create_task(schedule_auto_game_end(rid, reason=reason))

    return True


async def schedule_auto_game_end(rid: int, *, reason: str) -> None:
    await asyncio.sleep(5)

    r = get_redis()
    try:
        raw_state = await r.hgetall(f"room:{rid}:game_state")
    except Exception:
        log.exception("game_finish.auto_end.load_state_failed", rid=rid)
        return

    if not raw_state:
        return

    if str(raw_state.get("game_finished") or "0") != "1":
        return

    if str(raw_state.get("phase") or "idle") == "idle":
        return

    try:
        head_uid = int(raw_state.get("head") or 0)
    except Exception:
        head_uid = 0

    actor_uid = head_uid
    if actor_uid <= 0:
        try:
            members = await r.smembers(f"room:{rid}:members")
        except Exception:
            members = set()
        for v in (members or []):
            try:
                actor_uid = int(v)
            except Exception:
                continue
            if actor_uid:
                break

    sess: dict[str, Any] = {}
    if actor_uid:
        username: str | None = None
        try:
            raw_username = await r.hget(f"room:{rid}:user:{actor_uid}:info", "username")
        except Exception:
            raw_username = None
        if raw_username:
            username = str(raw_username)
        else:
            try:
                async with SessionLocal() as s:
                    row = await s.execute(select(User.username).where(User.id == actor_uid))
                    rec = row.first()
                    if rec and rec[0]:
                        username = str(rec[0])
            except Exception:
                log.exception("game_finish.auto_end.load_username_failed", rid=rid, uid=actor_uid)
        if username:
            sess["username"] = username

    ctx = GameActionContext.from_raw_state(uid=actor_uid or 0, rid=rid, r=r, raw_state=raw_state)
    try:
        await perform_game_end(ctx, sess, confirm=True, allow_non_head=True, reason=reason)
    except Exception:
        log.exception("game_finish.auto_end.failed", rid=rid)


async def finish_day_prelude_speech(r, rid: int, raw_gstate: Mapping[str, Any], speaker_uid: int, *, reason_override: str | None = None) -> dict[str, Any]:
    ctx = GameActionContext.from_raw_state(uid=speaker_uid, rid=rid, r=r, raw_state=raw_gstate)
    head_uid = ctx.head_uid

    best_move_uid = ctx.gint("best_move_uid")
    if best_move_uid:
        await log_game_action(
            r,
            rid,
            {
                "type": "best_move",
                "actor_id": best_move_uid,
                "targets": ctx.gcsv_ints("best_move_targets"),
                "day": get_day_number(raw_gstate),
            },
        )

    await process_player_death(r, rid, speaker_uid, head_uid=head_uid, phase_override="day", reason=reason_override or "night")

    if head_uid and speaker_uid != head_uid:
        try:
            await apply_blocks_and_emit(r, rid, actor_uid=head_uid, actor_role="head", target_uid=speaker_uid, changes_bool={"mic": True})
        except Exception:
            log.exception("day_prelude.finish.block_failed", rid=rid, head=head_uid, target=speaker_uid)

    async with r.pipeline() as p:
        await p.hset(
            f"room:{rid}:game_state",
            mapping={
                "day_current_uid": "0",
                "day_speech_started": "0",
                "day_speech_duration": "0",
                "day_prelude_active": "0",
                "day_prelude_done": "1",
                "night_kill_uid": "0",
                "night_kill_ok": "0",
                "day_prelude_uid": "0",
                "best_move_uid": "0",
                "best_move_active": "0",
                "best_move_targets": "",
            },
        )
        await p.execute()

    try:
        await sio.emit("game_best_move_update",
                       {"room_id": rid,
                        "best_move": {"uid": 0, "active": False, "targets": []}},
                       room=f"room:{rid}",
                       namespace="/room")
    except Exception:
        log.exception("day_prelude.best_move_clear_failed", rid=rid, uid=speaker_uid)

    return {
        "room_id": rid,
        "speaker_uid": speaker_uid,
        "opening_uid": 0,
        "closing_uid": 0,
        "deadline": 0,
        "prelude": True,
        "night": {"kill_uid": 0, "kill_ok": False},
        "vote_blocked": ctx.gbool("vote_blocked")
    }


def parse_leaders(raw_state: Mapping[str, Any]) -> list[int]:
    leaders_raw = str(raw_state.get("vote_leaders_order") or "")
    leaders: list[int] = []
    for part in leaders_raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            leaders.append(int(part))
        except Exception:
            continue

    return leaders


def should_block_vote_on_death(raw_state: Mapping[str, Any], victim_uid: int) -> tuple[bool, bool, list[int]]:
    phase = str(raw_state.get("phase") or "")
    vote_results_ready = str(raw_state.get("vote_results_ready") or "0") == "1"
    vote_lift_state = str(raw_state.get("vote_lift_state") or "")
    leaders = parse_leaders(raw_state)
    unique_leader = len(leaders) == 1

    if phase == "vote":
        if vote_lift_state == "voting":
            return True, False, leaders

        if not vote_results_ready or not unique_leader:
            return True, False, leaders

        if victim_uid in leaders:
            return True, False, leaders

        return False, True, leaders

    if phase == "day":
        return True, False, leaders

    if phase == "night":
        return False, True, leaders

    return False, True, leaders


def vote_leaders_from_counts(counts: Mapping[int, int]) -> list[int]:
    if not counts:
        return []

    max_votes = max(counts.values()) if counts else 0
    if max_votes <= 0:
        return []

    return [uid for uid, cnt in counts.items() if cnt == max_votes]


async def compute_vote_effective_leaders(r, rid: int, *, remaining_target_uid: int | None = None) -> list[int]:
    nominees = await get_nominees_in_order(r, rid)
    if not nominees:
        return []

    try:
        raw_votes = await hgetall_int_map(r, f"room:{rid}:game_votes")
    except Exception:
        raw_votes = {}

    counts: dict[int, int] = {uid: 0 for uid in nominees}
    for target in (raw_votes or {}).values():
        if target in counts:
            counts[target] = counts.get(target, 0) + 1

    if remaining_target_uid is not None:
        alive_ids, voted_ids = await get_alive_and_voted_ids(r, rid)
        current_uid = int(remaining_target_uid)
        if current_uid not in nominees:
            return vote_leaders_from_counts(counts)

        remaining_cnt = len(alive_ids - voted_ids)
        if current_uid in counts and remaining_cnt > 0:
            counts[current_uid] = counts.get(current_uid, 0) + remaining_cnt

    return vote_leaders_from_counts(counts)


async def decide_vote_blocks_on_death(r, rid: int, raw_state: Mapping[str, Any], victim_uid: int) -> tuple[bool, bool, list[int]]:
    phase = str(raw_state.get("phase") or "")
    if phase != "vote":
        return should_block_vote_on_death(raw_state, victim_uid)

    vote_lift_state = str(raw_state.get("vote_lift_state") or "")
    if vote_lift_state == "voting":
        return True, False, parse_leaders(raw_state)

    vote_results_ready = str(raw_state.get("vote_results_ready") or "0") == "1"
    if vote_results_ready:
        leaders_ready = parse_leaders(raw_state)
        if len(leaders_ready) == 1:
            if victim_uid in leaders_ready:
                return True, False, leaders_ready

            return False, True, leaders_ready

        return True, False, leaders_ready

    vote_done = str(raw_state.get("vote_done") or "0") == "1"
    if vote_done:
        leaders_done = await compute_vote_effective_leaders(r, rid, remaining_target_uid=None)
        if len(leaders_done) == 1:
            if victim_uid in leaders_done:
                return True, False, leaders_done

            return False, True, leaders_done

        return True, False, leaders_done

    nominees = await get_nominees_in_order(r, rid)
    if not nominees:
        return True, False, []

    try:
        current_uid = int(raw_state.get("vote_current_uid") or 0)
    except Exception:
        current_uid = 0
    if current_uid and current_uid in nominees:
        cur_idx = nominees.index(current_uid)
    else:
        current_uid = nominees[0]
        cur_idx = 0

    try:
        vote_started = int(raw_state.get("vote_started") or 0)
    except Exception:
        vote_started = 0

    try:
        vote_duration = int(raw_state.get("vote_duration") or 0)
    except Exception:
        vote_duration = 0
    if vote_duration <= 0:
        try:
            vote_duration = get_cached_settings().vote_seconds
        except Exception:
            vote_duration = 0

    last_pending = (cur_idx == len(nominees) - 1) and (vote_started == 0)
    if last_pending:
        leaders_pending = await compute_vote_effective_leaders(r, rid, remaining_target_uid=current_uid)
        if len(leaders_pending) == 1:
            if victim_uid in leaders_pending:
                return True, False, leaders_pending

            return False, True, leaders_pending

        return True, False, leaders_pending

    now_ts = int(time())
    vote_ended_for_current = bool(vote_started) and vote_duration > 0 and now_ts >= (vote_started + vote_duration)
    remaining_after_current = len(nominees) - (cur_idx + 1)
    if vote_ended_for_current and remaining_after_current == 1:
        remaining_uid = nominees[cur_idx + 1]
        leaders_remaining = await compute_vote_effective_leaders(r, rid, remaining_target_uid=remaining_uid)
        if len(leaders_remaining) == 1:
            if victim_uid in leaders_remaining:
                return True, False, leaders_remaining

            return False, True, leaders_remaining

        return True, False, leaders_remaining

    return True, False, []


async def block_vote_and_clear(r, rid: int, *, reason: str = "", phase: str = "") -> None:
    async with r.pipeline() as p:
        mapping = {"vote_blocked": "1"}
        if phase == "vote":
            mapping.update({
                "vote_done": "1",
                "vote_started": "0",
                "vote_aborted": "1",
                "vote_results_ready": "0",
                "vote_speeches_done": "0",
                "vote_prev_leaders": "",
                "vote_lift_state": "",
                "vote_leaders_order": "",
                "vote_leader_idx": "0",
                "vote_speech_uid": "0",
                "vote_speech_started": "0",
                "vote_speech_duration": "0",
                "vote_speech_kind": "",
                "vote_current_uid": "0",
            })
        await p.hset(f"room:{rid}:game_state", mapping=mapping)
        await p.delete(f"room:{rid}:game_nominees")
        await p.delete(f"room:{rid}:game_nom_speakers")
        if phase == "vote":
            await p.delete(f"room:{rid}:game_votes")
        await p.execute()

    payload = {"room_id": rid, "blocked": True, "reason": reason or "", "nominees": []}
    try:
        await sio.emit("game_vote_aborted",
                       payload,
                       room=f"room:{rid}",
                       namespace="/room")
    except Exception:
        log.exception("vote_blocked.emit_failed", rid=rid)


async def enrich_game_runtime_with_vote(r, rid: int, game_runtime: Mapping[str, Any], raw_gstate: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(game_runtime, dict) and "phase" in game_runtime:
        phase_cur = str(game_runtime.get("phase") or "idle")
    else:
        phase_cur = str(raw_gstate.get("phase") or "idle")

    ctx = GameActionContext.from_raw_state(uid=0, rid=rid, r=r, raw_state=raw_gstate, phase_override=phase_cur)
    if ctx.phase != "vote":
        return dict(game_runtime)

    if isinstance(game_runtime, dict):
        vote_section = dict(game_runtime.get("vote") or {})
        aborted = bool(vote_section.get("aborted"))
        results_ready = bool(vote_section.get("results_ready"))
    else:
        vote_section = {}
        aborted = ctx.gbool("vote_aborted")
        results_ready = ctx.gbool("vote_results_ready")

    if aborted or results_ready:
        vote_section.pop("voted", None)
        vote_section.pop("voted_for_current", None)
        out = dict(game_runtime)
        out["vote"] = vote_section
        return out

    current_nominee = ctx.gint("vote_current_uid")
    try:
        if isinstance(vote_section, dict):
            current_nominee = int(vote_section.get("current_uid") or current_nominee)
    except Exception:
        current_nominee = ctx.gint("vote_current_uid")

    raw_votes = await hgetall_int_map(r, f"room:{rid}:game_votes")
    voted_ids: list[int] = []
    voted_for_current: list[int] = []
    for voter, target in (raw_votes or {}).items():
        voted_ids.append(voter)
        if target and target == current_nominee:
            voted_for_current.append(voter)

    vote_section["voted"] = voted_ids
    vote_section["voted_for_current"] = voted_for_current
    out = dict(game_runtime)
    out["vote"] = vote_section
    return out


async def get_game_runtime_and_roles_view(r, rid: int, uid: int) -> tuple[dict[str, Any], dict[str, str], Optional[str]]:
    raw_gstate = await r.hgetall(f"room:{rid}:game_state")
    raw_game = await r.hgetall(f"room:{rid}:game")
    raw_seats = await hgetall_int_map(r, f"room:{rid}:game_seats")
    players_set = await smembers_ints(r, f"room:{rid}:game_players")
    alive_set = await smembers_ints(r, f"room:{rid}:game_alive")
    raw_roles = await r.hgetall(f"room:{rid}:game_roles")

    ctx = GameActionContext.from_raw_state(uid=uid, rid=rid, r=r, raw_state=raw_gstate)
    phase = ctx.phase
    seats_map: dict[str, int] = {str(uid): seat for uid, seat in (raw_seats or {}).items()}

    roles_map: dict[str, str] = {str(k): str(v) for k, v in (raw_roles or {}).items()}
    my_game_role = roles_map.get(str(uid))
    view = GameStateView(ctx, roles_map=roles_map, seats_map=seats_map)
    nominate_mode = str(raw_game.get("nominate_mode") or "players")
    if nominate_mode not in ("players", "head"):
        nominate_mode = "players"

    wink_knock = game_flag(raw_game, "wink_knock", True)
    farewell_wills_enabled = game_flag(raw_game, "farewell_wills", True)
    music_enabled = game_flag(raw_game, "music", True)
    winks_left = 0
    knocks_left = 0
    if phase != "idle" and wink_knock:
        try:
            winks_left = int(await r.hget(f"room:{rid}:game_winks_left", str(uid)) or 0)
        except Exception:
            winks_left = 0
        try:
            knocks_left = int(await r.hget(f"room:{rid}:game_knocks_left", str(uid)) or 0)
        except Exception:
            knocks_left = 0

    game_runtime: dict[str, Any] = {
        "phase": phase,
        "min_ready": get_cached_settings().game_min_ready_players,
        "seats": seats_map,
        "players": list(players_set),
        "alive": list(alive_set),
        "bgm_seed": ctx.gint("bgm_seed"),
        "host_blur": ctx.gbool("host_blur"),
        "nominate_mode": nominate_mode,
        "wink_knock": wink_knock,
        "farewell_wills_enabled": farewell_wills_enabled,
        "music": music_enabled,
        "winks_left": winks_left,
        "knocks_left": knocks_left,
    }

    finished = ctx.gbool("game_finished")
    if finished:
        game_runtime["finished"] = True
        game_runtime["result"] = ctx.gstr("game_result")

    if phase == "idle":
        return game_runtime, {}, None

    if my_game_role in ("don", "sheriff"):
        checked_key = f"room:{rid}:game_checked:{my_game_role}"
        checked_ids = list(await smembers_ints(r, checked_key))
        known: dict[str, str] = {}
        for tu in checked_ids:
            tr = roles_map.get(str(tu)) or ""
            if my_game_role == "sheriff":
                known[str(tu)] = "mafia" if tr in ("mafia", "don") else "citizen"
            else:
                known[str(tu)] = "sheriff" if tr == "sheriff" else "citizen"
        game_runtime["checks"] = {"checked": checked_ids, "known": known}

    if phase == "roles_pick":
        roles_pick_section = await view.roles_pick(r, rid)
        if roles_pick_section:
            game_runtime["roles_pick"] = roles_pick_section

    if phase == "mafia_talk_start":
        mafia_section = view.mafia_talk()
        if mafia_section:
            game_runtime["mafia_talk_start"] = mafia_section

    if phase == "day":
        day_section = await view.day(r, rid, uid)
        if day_section:
            game_runtime["day"] = day_section

    if phase == "vote":
        vote_section = await view.vote(r, rid)
        if vote_section:
            game_runtime["vote"] = vote_section

    if phase == "night":
        night_section = await view.night(r, rid, uid)
        if night_section:
            game_runtime["night"] = night_section

    try:
        farewell_wills = await get_farewell_wills(r, rid)
        if farewell_wills:
            game_runtime["farewell_wills"] = farewell_wills
    except Exception:
        log.exception("game_runtime.farewell_wills_failed", rid=rid)

    try:
        farewell_limits = await get_farewell_limits(r, rid)
        if farewell_limits:
            game_runtime["farewell_limits"] = farewell_limits
    except Exception:
        log.exception("game_runtime.farewell_limits_failed", rid=rid)

    best_move = best_move_payload_from_state(ctx)
    if best_move is not None:
        game_runtime["best_move"] = best_move
        if best_move.get("active"):
            try:
                killed_uid, ok = await compute_night_kill(r, rid, log_action_bool=False)
                game_runtime["best_move_night"] = {"kill_uid": killed_uid, "kill_ok": ok}
            except Exception:
                log.exception("game_runtime.best_move_night_failed", rid=rid)

    head_uid = ctx.head_uid
    roles_done = ctx.gbool("roles_done")
    game_roles_view: dict[str, str] = {}
    if finished:
        game_roles_view = dict(roles_map)
    elif roles_done:
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
        raw_nominees = await hgetall_int_map(r, f"room:{rid}:game_nominees")
    except Exception:
        raw_nominees = {}

    tmp: list[tuple[int, int]] = []
    for uid, idx in (raw_nominees or {}).items():
        if idx > 0:
            tmp.append((idx, uid))

    if not tmp:
        return []

    tmp.sort(key=lambda t: t[0])

    return [u for _, u in tmp]


async def get_alive_and_voted_ids(r, rid: int) -> tuple[set[int], set[int]]:
    alive_ids = await smembers_ints(r, f"room:{rid}:game_alive")
    voted_ids = await hkeys_ints(r, f"room:{rid}:game_votes")
    return alive_ids, voted_ids


def can_act_on_user(actor_role: str, target_role: str) -> bool:
    if actor_role not in ("admin", "host"):
        return False

    if actor_role == "host" and target_role == "admin":
        return False

    if actor_role == target_role:
        return False

    return True


async def stop_screen_for_user(r, rid: int, uid: int, *, canceled: bool = False, actor_uid: int | None = None, actor_username: str | None = None, actor_role: str | None = None) -> None:
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

    try:
        log_uid = actor_uid if actor_uid is not None else uid
        log_username = actor_username or f"user{log_uid}"
        try:
            target_username = await r.hget(f"room:{rid}:user:{uid}:info", "username")
        except Exception:
            target_username = None
        details = f"Остановка стрима room_id={rid} target_user={uid}"
        if target_username:
            details += f" target_username={target_username}"
        if actor_uid is not None and actor_uid != uid:
            details += f" actor_user={actor_uid}"
            if actor_username:
                details += f" actor_username={actor_username}"
            if actor_role:
                details += f" actor_role={actor_role}"
        async with SessionLocal() as s:
            await log_action(
                s,
                user_id=log_uid,
                username=log_username,
                action="stream_stop",
                details=details,
            )
    except Exception:
        log.exception("sio.stream_stop.log_failed", rid=rid, uid=uid, actor=actor_uid)


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


async def emit_mafia_filtered(event: str, payload: dict[str, Any], r, rid: int, subject_uid: int, *, phase_override: str | None = None) -> None:
    is_mafia_talk, viewers = await get_mafia_talk_viewers(r, rid, subject_uid, phase_override)
    if not is_mafia_talk:
        await sio.emit(event, payload, room=f"room:{rid}", namespace="/room")
        return

    for uid in viewers:
        await sio.emit(event, payload, room=f"user:{uid}", namespace="/room")


async def emit_state_changed_filtered(r, rid: int, subject_uid: int, changed: dict[str, str], *, phase_override: str | None = None) -> None:
    payload = {"user_id": subject_uid, **changed}
    await emit_mafia_filtered("state_changed", payload, r, rid, subject_uid, phase_override=phase_override)


async def emit_moderation_filtered(r, rid: int, target_uid: int, blocks_full: dict[str, str], actor_uid: int, actor_role: str, *, phase_override: str | None = None) -> None:
    payload = {
        "user_id": target_uid,
        "blocks": blocks_full,
        "by": {"user_id": actor_uid, "role": actor_role},
    }
    await emit_mafia_filtered("moderation", payload, r, rid, target_uid, phase_override=phase_override)


async def record_spectator_leave(r, rid: int, uid: int, now_ts: int) -> None:
    try:
        raw_join = await r.hget(f"room:{rid}:spectators_join", str(uid))
    except Exception:
        raw_join = None
    if raw_join:
        try:
            join_ts = int(raw_join or 0)
        except Exception:
            join_ts = 0
        dt = now_ts - join_ts
        if dt > 0:
            try:
                await r.hincrby(f"room:{rid}:spectators_time", str(uid), dt)
            except Exception:
                log.warning("spectator.leave.time_failed", rid=rid, uid=uid)
    try:
        await r.hdel(f"room:{rid}:spectators_join", str(uid))
    except Exception:
        log.warning("spectator.leave.join_cleanup_failed", rid=rid, uid=uid)
    try:
        await r.srem(f"room:{rid}:spectators", str(uid))
    except Exception:
        log.warning("spectator.leave.remove_failed", rid=rid, uid=uid)
    await clear_user_current_room(r, uid, rid=rid)
    await emit_rooms_spectators_safe(r, rid)


async def bump_friend_closeness(session: AsyncSession, user_ids: Iterable[int]) -> None:
    ids = sorted({int(x) for x in user_ids if int(x) > 0})
    if len(ids) < 2:
        return

    values: list[dict[str, int]] = []
    for i in range(0, len(ids)):
        for j in range(i + 1, len(ids)):
            values.append({"user_low": ids[i], "user_high": ids[j], "games_together": 1})

    if not values:
        return

    stmt = insert(FriendCloseness).values(values)
    stmt = stmt.on_conflict_do_update(index_elements=["user_low", "user_high"],
                                      set_={"games_together": FriendCloseness.games_together + stmt.excluded.games_together,
                                            "updated_at": func.now()})
    await session.execute(stmt)


async def perform_game_end(ctx, sess: Optional[dict[str, Any]], *, confirm: bool, allow_non_head: bool = False, reason: str = "manual") -> dict[str, Any]:
    uid = ctx.uid
    rid = ctx.rid
    r = ctx.r
    phase = ctx.phase
    sess = sess or {}
    if phase == "idle":
        return {"ok": False, "error": "no_game", "status": 400}

    head_uid = ctx.head_uid
    if not head_uid:
        if not allow_non_head:
            return {"ok": False, "error": "forbidden", "status": 403}

        head_uid = uid

    if not allow_non_head and uid != head_uid:
        return {"ok": False, "error": "forbidden", "status": 403}

    if not confirm:
        return {"ok": True, "status": 200, "room_id": rid, "can_end": True}     

    game_result = ctx.gstr("game_result")
    black_alive: int | None = None
    if game_result == "black" or reason == "victory_black":
        try:
            alive_ids = await smembers_ints(r, f"room:{rid}:game_alive")
        except Exception:
            log.exception("sio.game_end.load_alive_failed", rid=rid)
            alive_ids = set()
        try:
            raw_roles = await r.hgetall(f"room:{rid}:game_roles")
        except Exception:
            log.exception("sio.game_end.load_roles_failed", rid=rid)
            raw_roles = {}

        black_alive = 0
        for alive_uid in alive_ids:
            role = str(raw_roles.get(str(alive_uid)) or "")
            if role in ("mafia", "don"):
                black_alive += 1

    try:
        players_set = await r.smembers(f"room:{rid}:game_players")
    except Exception:
        log.exception("sio.game_end.load_players_failed", rid=rid)
        players_set = set()

    players_list: list[int] = []
    for v in (players_set or []):
        try:
            players_list.append(int(v))
        except Exception:
            continue

    try:
        members_set = await r.smembers(f"room:{rid}:members")
    except Exception:
        log.exception("sio.game_end.load_members_failed", rid=rid)
        members_set = set()

    member_ids: set[int] = set()
    for v in (members_set or []):
        try:
            member_ids.add(int(v))
        except Exception:
            continue

    for target_uid in players_list:
        if target_uid == head_uid:
            continue

        try:
            await apply_blocks_and_emit(r, rid, actor_uid=head_uid, actor_role="head", target_uid=target_uid, phase_override="idle",
                                        changes_bool={"mic": False, "cam": False, "speakers": False, "visibility": False})
        except Exception:
            log.exception("sio.game_end.auto_unblock_failed", rid=rid, head=head_uid, target=target_uid)

        if target_uid not in member_ids:
            continue

        try:
            new_state = await apply_state(r, rid, target_uid, {"mic": False, "cam": True, "speakers": True, "visibility": True})
            if new_state:
                await emit_state_changed_filtered(r, rid, target_uid, new_state, phase_override="idle")
        except Exception:
            log.exception("sio.game_end.auto_state_enable_failed", rid=rid, target=target_uid)

    async with r.pipeline() as p:
        await p.delete(
            f"room:{rid}:game_state",
            f"room:{rid}:game_seats",
            f"room:{rid}:game_players",
            f"room:{rid}:game_alive",
            f"room:{rid}:game_fouls",
            f"room:{rid}:game_deaths",
            f"room:{rid}:game_actions",
            f"room:{rid}:game_votes_last",
            f"room:{rid}:game_short_speech_used",
            f"room:{rid}:game_nominees",
            f"room:{rid}:game_nom_speakers",
            f"room:{rid}:roles_cards",
            f"room:{rid}:roles_taken",
            f"room:{rid}:game_roles",
            f"room:{rid}:game_votes",
            f"room:{rid}:night_shots",
            f"room:{rid}:night_checks",
            f"room:{rid}:game_checked:don",
            f"room:{rid}:game_checked:sheriff",
            f"room:{rid}:game_farewell_wills",
            f"room:{rid}:game_farewell_limits",
            f"room:{rid}:game_winks_left",
            f"room:{rid}:game_knocks_left",
        )
        await p.execute()

    try:
        occ = int(await r.scard(f"room:{rid}:members") or 0)
    except Exception:
        occ = 0

    await sio.emit("rooms_occupancy",
                   {"id": rid,
                    "occupancy": occ},
                   namespace="/rooms")

    try:
        briefs = await get_rooms_brief(r, [rid])
        if briefs:
            await sio.emit("rooms_upsert",
                           briefs[0],
                           namespace="/rooms")
    except Exception:
        log.exception("sio.game_end.rooms_upsert_failed", rid=rid)

    try:
        raw_spec_join = await r.hgetall(f"room:{rid}:spectators_join")
        if raw_spec_join:
            now_ts = int(time())
            for k, v in raw_spec_join.items():
                try:
                    uid_i = int(k)
                    join_ts = int(v or 0)
                except Exception:
                    continue
                dt = now_ts - join_ts
                if dt > 0:
                    try:
                        await r.hincrby(f"room:{rid}:spectators_time", str(uid_i), dt)
                    except Exception:
                        log.warning("game_end.spectators_time.flush_failed", rid=rid, uid=uid_i)
    except Exception:
        log.exception("sio.game_end.spectators_join_failed", rid=rid)

    try:
        spectators = await r.smembers(f"room:{rid}:spectators")
    except Exception:
        spectators = set()
    if spectators:
        for v in spectators:
            try:
                uid_i = int(v)
            except Exception:
                continue
            await sio.emit("force_leave",
                           {"room_id": rid, "reason": "game_end"},
                           room=f"user:{uid_i}",
                           namespace="/room")
    try:
        await r.delete(f"room:{rid}:spectators", f"room:{rid}:spectators_join")
    except Exception:
        log.exception("sio.game_end.spectators_clear_failed", rid=rid)
    await emit_rooms_spectators_safe(r, rid)

    await sio.emit("game_ended",
                   {"room_id": rid, "reason": reason},
                   room=f"room:{rid}",
                   namespace="/room")

    try:
        async with SessionLocal() as s:
            details = f"Завершение игры room_id={rid} phase={phase} reason={reason}"
            if black_alive is not None:
                details += f" black_alive={black_alive}"
            await log_action(
                s,
                user_id=uid,
                username=str(sess.get("username") or f"user{uid}"),
                action="game_end",
                details=details)
    except Exception:
        log.exception("sio.game_end.log_failed", rid=rid, uid=uid)

    return {"ok": True, "status": 200, "room_id": rid, "reason": reason}


async def gc_empty_room(rid: int, *, expected_seq: int | None = None) -> bool:
    r = get_redis()
    ts1 = await r.get(f"room:{rid}:empty_since")
    if not ts1:
        log.warning("gc.skip.no_empty_since", rid=rid)
        return False

    ttl_seconds = max(0, int(get_cached_settings().rooms_empty_ttl_seconds))
    delay = max(0, ttl_seconds - (int(time()) - int(ts1)))
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

        raw_spec_join = await r.hgetall(f"room:{rid}:spectators_join")
        if raw_spec_join:
            now_ts = int(time())
            for k, v in raw_spec_join.items():
                try:
                    uid_i = int(k)
                    join_ts = int(v or 0)
                except Exception:
                    continue
                dt = now_ts - join_ts
                if dt > 0:
                    try:
                        await r.hincrby(f"room:{rid}:spectators_time", str(uid_i), dt)
                    except Exception:
                        log.warning("gc.spectators_time.flush_failed", rid=rid, uid=uid_i)

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

        raw_spec = await r.hgetall(f"room:{rid}:spectators_time")
        spectators_map_sec: dict[int, int] = {}
        for k, v in (raw_spec or {}).items():
            try:
                spectators_map_sec[int(k)] = int(v or 0)
            except Exception:
                continue

        unique_user_ids = set(visitors_map.keys()) | set(screen_map_sec.keys()) | set(spectators_map_sec.keys())
        unique_user_count = len(unique_user_ids)
        try:
            async with SessionLocal() as s:
                rm = await s.get(Room, rid)
                if rm:
                    rm_title = rm.title
                    rm_creator = cast(int, rm.creator)
                    rm_creator_name = cast(str, rm.creator_name)
                    unique_visitors = len(set(visitors_map.keys()))

                    now_dt = datetime.now(timezone.utc)
                    screen_time_patch = {str(uid): max(0, sec) for uid, sec in screen_map_sec.items()}
                    merged_screen_time = {**(rm.screen_time or {}), **screen_time_patch}
                    spectators_time_patch = {str(uid): max(0, sec) for uid, sec in spectators_map_sec.items()}
                    merged_spectators_time = {**(rm.spectators_time or {}), **spectators_time_patch}

                    if unique_user_count <= 1:
                        details = f"Удаление комнаты room_id={rid} title={rm_title} count_users={unique_visitors}"
                        await log_action(
                            s,
                            user_id=rm_creator,
                            username=rm_creator_name,
                            action="room_deleted",
                            details=details,
                            commit=False,
                        )
                        await s.execute(delete(Room).where(Room.id == rid))
                        await s.commit()
                        await r.srem(f"user:{rm_creator}:rooms", str(rid))
                        log.info("gc.room.purged_single_user", rid=rid, creator=rm_creator)
                    else:
                        try:
                            lifetime_sec = int((now_dt - rm.created_at).total_seconds())
                        except Exception:
                            lifetime_sec = None
                        total_stream_sec = 0
                        for v in merged_screen_time.values():
                            try:
                                total_stream_sec += int(v or 0)
                            except Exception:
                                continue
                        games_count = 0
                        try:
                            res = await s.execute(select(func.count(Game.id)).where(Game.room_id == rid))
                            games_count = int(res.scalar() or 0)
                        except Exception:
                            log.exception("gc.room_games_count_failed", rid=rid)
                        
                        rm.visitors = {**(rm.visitors or {}), **{str(k): v for k, v in visitors_map.items()}}
                        rm.screen_time = merged_screen_time
                        rm.spectators_time = merged_spectators_time
                        rm.deleted_at = now_dt
                        
                        await r.srem(f"user:{rm_creator}:rooms", str(rid))
                        details = f"Удаление комнаты room_id={rid} title={rm_title} count_users={unique_visitors}"
                        if lifetime_sec is not None:
                            details += f" lifetime_sec={lifetime_sec}"
                        details += f" total_stream_sec={total_stream_sec}"
                        if games_count > 0:
                            details += f" games_count={games_count}"
                        await log_action(
                            s,
                            user_id=rm_creator,
                            username=rm_creator_name,
                            action="room_deleted",
                            details=details,
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
            f"room:{rid}:spectators",
            f"room:{rid}:spectators_time",
            f"room:{rid}:spectators_join",
            f"room:{rid}:gc_seq",
            f"room:{rid}:empty_since",
            f"room:{rid}:gc_lock",
            f"room:{rid}:allow",
            f"room:{rid}:pending",
            f"room:{rid}:requests",
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
