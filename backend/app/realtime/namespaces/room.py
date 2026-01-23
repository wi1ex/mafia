from __future__ import annotations
import asyncio
import random
from time import time
from typing import Any
import structlog
from ..sio import sio
from ...core.clients import get_redis
from ...security.decorators import rate_limited_sio
from ...core.logging import log_action
from ...core.db import SessionLocal
from ...security.parameters import get_cached_settings
from ...schemas.realtime import StateAck, ModerateAck, JoinAck, ScreenAck, GameStartAck, GameRolePickAck
from ...services.livekit import make_livekit_token
from ..utils import (
    SANCTION_TIMEOUT,
    SANCTION_BAN,
    SANCTION_SUSPEND,
    fetch_active_sanctions,
    fetch_active_users_by_kind,
)
from ..utils import (
    KEYS_STATE,
    KEYS_BLOCK,
    apply_state,
    apply_bg_state_on_join,
    apply_join_idle_defaults,
    apply_join_phase_state,
    extract_state_mapping,
    get_user_state_and_block,
    gc_empty_room,
    get_room_snapshot,
    merge_ready_into_snapshot,
    set_ready,
    get_positions_map,
    game_flag,
    persist_join_user_info,
    get_blocks_snapshot,
    get_roles_snapshot,
    get_profiles_snapshot,
    join_room_atomic,
    leave_room_atomic,
    validate_auth,
    claim_screen,
    get_rooms_brief,
    init_roles_deck,
    advance_roles_turn,
    assign_role_for_user,
    emit_rooms_occupancy_safe,
    emit_rooms_spectators_safe,
    get_game_runtime_and_roles_view,
    emit_state_changed_filtered,
    stop_screen_for_user,
    GameActionContext,
    compute_day_opening_and_closing,
    recompute_day_opening_and_closing_from_state,
    get_alive_players_in_seat_order,
    get_players_in_seat_order,
    schedule_foul_block,
    maybe_block_foul_on_reconnect,
    emit_game_fouls,
    apply_blocks_and_emit,
    finish_day_speech,
    get_nominees_in_order,
    get_alive_and_voted_ids,
    enrich_game_runtime_with_vote,
    get_game_fouls,
    finish_vote_speech,
    emit_game_night_state,
    night_stage_timeout_job,
    compute_night_kill,
    best_move_payload_from_state,
    build_night_reset_mapping,
    apply_night_start_blocks,
    apply_day_visibility_unblock,
    finish_day_prelude_speech,
    emit_night_head_picks,
    process_player_death,
    require_ctx,
    ensure_can_act_role,
    get_game_deaths,
    get_farewell_wills,
    get_farewell_limits,
    get_farewell_wills_for,
    ensure_farewell_limit,
    log_game_action,
    store_last_votes_snapshot,
    block_vote_and_clear,
    decide_vote_blocks_on_death,
    get_positive_setting_int,
    compute_farewell_allowed,
    perform_game_end,
    finish_game,
    record_spectator_leave,
)

log = structlog.get_logger()


@sio.event(namespace="/room")
async def connect(sid, environ, auth):
    vr = await validate_auth(auth)
    if not vr:
        log.warning("room.connect.denied", sid=sid)
        return False

    uid, role, username, avatar_name = vr
    await sio.save_session(sid,
                           {"uid": uid,
                            "rid": None,
                            "role": role,
                            "base_role": role,
                            "username": username,
                            "avatar_name": avatar_name},
                           namespace="/room")
    await sio.enter_room(sid,
                         f"user:{uid}",
                         namespace="/room")


@rate_limited_sio(lambda *, uid=None, **__: f"rl:sio:join:{uid or 'nouid'}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def join(sid, data) -> JoinAck:
    try:
        sess = await sio.get_session(sid, namespace="/room")
        uid = int(sess["uid"])
        base_role = str(sess.get("base_role") or "user")
        rid = int((data or {}).get("room_id") or 0)
        if not rid:
            log.warning("sio.join.bad_room_id", sid=sid)
            return {"ok": False, "error": "bad_room_id", "status": 400}

        r = get_redis()
        params = await r.hgetall(f"room:{rid}:params")
        if not params:
            return {"ok": False, "error": "room_not_found", "status": 404}      

        if str(params.get("entry_closed") or "0") == "1":
            return {"ok": False, "error": "room_closed", "status": 410}

        if not get_cached_settings().rooms_can_enter:
            return {"ok": False, "error": "rooms_entry_disabled", "status": 403}

        async with SessionLocal() as s:
            active = await fetch_active_sanctions(s, uid)
            if active.get(SANCTION_BAN):
                return {"ok": False, "error": "user_banned", "status": 403}

            if active.get(SANCTION_TIMEOUT):
                return {"ok": False, "error": "user_timeout", "status": 403}

        allowed = True
        pending = False
        is_private = (params.get("privacy") or "open") == "private"
        is_creator = int(params.get("creator") or 0) == uid
        if is_private and not is_creator:
            allowed = await r.sismember(f"room:{rid}:allow", str(uid))
            if not allowed:
                pending = await r.sismember(f"room:{rid}:pending", str(uid))

        raw_gstate = await r.hgetall(f"room:{rid}:game_state")
        phase = str(raw_gstate.get("phase") or "idle")
        if is_private and not is_creator and not allowed and phase == "idle":
            return {"ok": False, "error": "private_room", "status": 403, "pending": bool(pending)}

        spectator_mode = False
        spectator_added = False
        if phase != "idle":
            head_raw = raw_gstate.get("head")
            head_id = int(head_raw) if head_raw else 0
            game_players_set = await r.smembers(f"room:{rid}:game_players")
            allowed_ids = {head_id} | {int(x) for x in (game_players_set or [])}
            if uid not in allowed_ids:
                try:
                    raw_game = await r.hgetall(f"room:{rid}:game")
                except Exception:
                    raw_game = {}
                try:
                    spectators_limit = int(raw_game.get("spectators_limit") or 0)
                except Exception:
                    spectators_limit = 0
                if spectators_limit <= 0:
                    return {"ok": False, "error": "game_in_progress", "status": 409}

                try:
                    already_spectator = await r.sismember(f"room:{rid}:spectators", str(uid))
                except Exception:
                    already_spectator = False
                if not already_spectator:
                    try:
                        spectators_count = int(await r.scard(f"room:{rid}:spectators") or 0)
                    except Exception:
                        spectators_count = 0
                    if spectators_count >= spectators_limit:
                        return {"ok": False, "error": "spectators_full", "status": 409}

                    spectator_added = bool(await r.sadd(f"room:{rid}:spectators", str(uid)))

                spectator_mode = True
                try:
                    await r.hset(f"room:{rid}:spectators_join", mapping={str(uid): str(int(time()))})
                except Exception:
                    log.warning("spectator.join_time_failed", rid=rid, uid=uid)
                if spectator_added:
                    await emit_rooms_spectators_safe(r, rid)

        occ = 0
        pos = 0
        already = False
        pos_updates = []
        if not spectator_mode:
            occ, pos, already, pos_updates = await join_room_atomic(r, rid, uid, base_role)
            if occ == -3:
                log.warning("sio.join.room_closed", rid=rid, uid=uid)
                return {"ok": False, "error": "room_closed", "status": 410}

            if occ == -1:
                log.warning("sio.join.room_full", rid=rid, uid=uid)
                return {"ok": False, "error": "room_is_full", "status": 409}

        await persist_join_user_info(r, rid, uid, sess.get("username"), sess.get("avatar_name"))

        try:
            foul_removed = int(await r.hdel(f"room:{rid}:foul_active", str(uid)) or 0)
        except Exception:
            foul_removed = 0
            log.warning("sio.join.clear_foul_active_failed", rid=rid, uid=uid)
        if foul_removed and not spectator_mode:
            await maybe_block_foul_on_reconnect(r, rid, uid, raw_gstate)

        try:
            await r.srem(f"room:{rid}:ready", str(uid))
        except Exception:
            log.warning("sio.join.ready_reset_failed", rid=rid, uid=uid)
        await sio.enter_room(sid,
                             f"room:{rid}",
                             namespace="/room")

        snapshot = await get_room_snapshot(r, rid)
        snapshot = await merge_ready_into_snapshot(r, rid, snapshot)
        blocked = await get_blocks_snapshot(r, rid)
        roles = await get_roles_snapshot(r, rid)

        extra_profile_ids: list[str] = []
        if phase != "idle":
            try:
                extra_profile_ids = list(await r.hkeys(f"room:{rid}:game_seats") or [])
            except Exception:
                extra_profile_ids = []
            if not extra_profile_ids:
                try:
                    extra_profile_ids = list(await r.smembers(f"room:{rid}:game_players") or [])
                except Exception:
                    extra_profile_ids = []
        profiles = await get_profiles_snapshot(r, rid, extra_ids=extra_profile_ids)

        if phase == "mafia_talk_start":
            raw_game_roles = await r.hgetall(f"room:{rid}:game_roles")
            my_game_role_full = str(raw_game_roles.get(str(uid)) or "")
            try:
                head_id = int(raw_gstate.get("head") or 0)
            except Exception:
                head_id = 0

            is_head = uid == head_id
            is_mafia_team = my_game_role_full in ("mafia", "don")

            if not (is_head or is_mafia_team):
                safe_snapshot: dict[str, dict[str, str]] = {}
                for k, st in (snapshot or {}).items():
                    uk = str(k)
                    if uk == str(uid):
                        safe_snapshot[uk] = dict(st or {})
                    else:
                        ns = dict(st or {})
                        if "visibility" in ns:
                            ns["visibility"] = "1"
                        safe_snapshot[uk] = ns
                snapshot = safe_snapshot

                safe_blocked: dict[str, dict[str, str]] = {}
                for k, bl in (blocked or {}).items():
                    uk = str(k)
                    if uk == str(uid):
                        safe_blocked[uk] = dict(bl or {})
                    else:
                        nb = dict(bl or {})
                        if "visibility" in nb:
                            nb["visibility"] = "0"
                        safe_blocked[uk] = nb
                blocked = safe_blocked

        me_prof = profiles.get(str(uid)) or {}
        ev_username = me_prof.get("username") or sess.get("username") or f"user{uid}"
        ev_avatar = me_prof.get("avatar_name") or sess.get("avatar_name") or None
        eff_role = roles.get(str(uid), base_role)

        epoch = int(await r.incr(f"room:{rid}:user:{uid}:epoch"))
        exp_ok = await r.expire(f"room:{rid}:user:{uid}:epoch", 86400)
        if not exp_ok:
            log.warning("sio.join.epoch_expire_not_set", rid=rid, uid=uid)

        await sio.save_session(sid,
                               {"uid": uid,
                                "rid": rid,
                                "role": eff_role,
                                "base_role": base_role,
                                "username": ev_username,
                                "avatar_name": ev_avatar,
                                "epoch": epoch,
                                "spectator": spectator_mode},
                               namespace="/room")

        user_state: dict[str, str] = {}
        if not spectator_mode:
            incoming = (data.get("state") or {}) if isinstance(data, dict) else {}
            user_state = {k: str(v) for k, v in (snapshot.get(str(uid)) or {}).items()}
            to_fill = {k: incoming[k] for k in KEYS_STATE if k in incoming and k not in user_state}
            if to_fill:
                applied = await apply_state(r, rid, uid, to_fill)
                if applied:
                    user_state = {**user_state, **applied}
                    snapshot[str(uid)] = user_state
                    await emit_state_changed_filtered(r, rid, uid, applied)

            if phase == "idle":
                applied_bg, had_bg_state = await apply_bg_state_on_join(r, rid, uid)
                if applied_bg:
                    user_state = {**user_state, **applied_bg}
                    snapshot[str(uid)] = user_state

                if not had_bg_state:
                    applied2 = await apply_join_idle_defaults(r, rid, uid, user_state=user_state, blocked=blocked)
                    if applied2:
                        user_state = {**user_state, **applied2}
                        snapshot[str(uid)] = user_state

            if phase != "idle":
                applied_rules = await apply_join_phase_state(r, rid, uid, phase=phase, raw_gstate=raw_gstate, blocked=blocked)
                if applied_rules:
                    user_state = {**user_state, **applied_rules}
                    snapshot[str(uid)] = user_state

            if not already:
                await emit_rooms_occupancy_safe(r, rid, occ)

            await sio.emit("member_joined",
                           {"user_id": uid,
                            "state": user_state,
                            "role": eff_role,
                            "blocks": blocked.get(str(uid)) or {},
                            "username": ev_username,
                            "avatar_name": ev_avatar},
                           room=f"room:{rid}",
                           skip_sid=sid,
                           namespace="/room")

            if pos_updates:
                await sio.emit("positions",
                               {"updates": [{"user_id": u, "position": p} for u, p in pos_updates]},
                               room=f"room:{rid}",
                               namespace="/room")

            await sio.emit("positions",
                           {"updates": [{"user_id": uid, "position": pos}]},
                           room=f"room:{rid}",
                           skip_sid=sid,
                           namespace="/room")

        try:
            user_limit = int(params.get("user_limit") or 0)
        except Exception:
            user_limit = 0

        positions = await get_positions_map(r, rid)
        owner_raw = await r.get(f"room:{rid}:screen_owner")
        owner = int(owner_raw) if owner_raw else 0
        token = make_livekit_token(identity=str(uid), name=ev_username, room=str(rid), can_publish=not spectator_mode)
        game_runtime, game_roles_view, my_game_role = await get_game_runtime_and_roles_view(r, rid, uid)
        game_runtime = await enrich_game_runtime_with_vote(r, rid, game_runtime, raw_gstate)
        game_fouls = await get_game_fouls(r, rid)
        game_deaths = await get_game_deaths(r, rid)
        farewell_wills = await get_farewell_wills(r, rid)
        farewell_limits = await get_farewell_limits(r, rid)

        payload = {
            "ok": True,
            "room_id": rid,
            "token": token,
            "privacy": str(params.get("privacy") or "open"),
            "user_limit": user_limit,
            "snapshot": snapshot,
            "self_pref": user_state,
            "positions": positions,
            "blocked": blocked,
            "roles": roles,
            "profiles": profiles,
            "screen_owner": owner,
            "game_runtime": game_runtime,
            "game_roles": game_roles_view,
            "my_game_role": my_game_role,
            "game_fouls": game_fouls,
            "game_deaths": game_deaths,
            "farewell_wills": farewell_wills,
            "farewell_limits": farewell_limits,
        }

        return payload

    except Exception:
        log.exception("sio.join.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:state:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def state(sid, data) -> StateAck:
    try:
        sess = await sio.get_session(sid, namespace="/room")
        uid = int(sess["uid"])
        rid = int(sess.get("rid") or 0)
        if not rid:
            log.warning("sio.state.no_rid", uid=uid)
            return {"ok": False}

        r = get_redis()
        is_spectator = bool(sess.get("spectator"))
        if not is_spectator:
            try:
                is_spectator = await r.sismember(f"room:{rid}:spectators", str(uid))
            except Exception:
                is_spectator = False
        if is_spectator:
            return {"ok": True}

        payload = data or {}
        applied = await apply_state(r, rid, uid, payload)
        changed = dict(applied)
        if "ready" in payload:
            newv = await set_ready(r, rid, uid, payload.get("ready"))
            if newv is not None:
                changed["ready"] = newv
        if changed:
            await emit_state_changed_filtered(r, rid, uid, changed)
        return {"ok": True}

    except Exception:
        log.exception("sio.state.error", sid=sid)
        return {"ok": False}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:bg_state:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def bg_state(sid, data):
    try:
        ctx, err = await require_ctx(sid, allowed_phases="idle")
        if err:
            return err

        sess = await sio.get_session(sid, namespace="/room")
        if sess.get("spectator"):
            return {"ok": True}

        payload = data or {}
        states = payload.get("state") if isinstance(payload, dict) else None
        if not isinstance(states, dict):
            return {"ok": False, "error": "bad_state", "status": 400}

        def to01(var: Any) -> str:
            if isinstance(var, bool):
                return "1" if var else "0"

            s = str(var).strip().lower()
            return "1" if s in {"1", "true"} else "0"

        mapping: dict[str, str] = {}
        for k, v in states.items():
            if k in KEYS_STATE:
                mapping[k] = to01(v)

        if not mapping:
            return {"ok": True, "saved": False}

        r = ctx.r
        key = f"room:{ctx.rid}:user:{ctx.uid}:bg_state"
        await r.hset(key, mapping=mapping)
        await r.expire(key, 600)

        return {"ok": True, "saved": True}

    except Exception:
        log.exception("sio.bg_state.error", sid=sid)
        return {"ok": False}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:bg_restore:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def bg_restore(sid, data):
    try:
        ctx, err = await require_ctx(sid, allowed_phases="idle")
        if err:
            return err

        sess = await sio.get_session(sid, namespace="/room")
        if sess.get("spectator"):
            return {"ok": True}

        r = ctx.r
        key = f"room:{ctx.rid}:user:{ctx.uid}:bg_state"
        raw = await r.hgetall(key)
        if not raw:
            return {"ok": True, "state": None}

        states = extract_state_mapping(raw, KEYS_STATE)
        applied = await apply_state(r, ctx.rid, ctx.uid, states)
        if applied:
            await emit_state_changed_filtered(r, ctx.rid, ctx.uid, applied)
        effective, blocked = await get_user_state_and_block(r, ctx.rid, ctx.uid)
        try:
            await r.delete(key)
        except Exception:
            log.warning("sio.bg_state.delete_failed", rid=ctx.rid, uid=ctx.uid)

        return {"ok": True, "state": effective, "blocked": blocked}

    except Exception:
        log.exception("sio.bg_restore.error", sid=sid)
        return {"ok": False}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:self_state:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def self_state(sid, data):
    try:
        ctx, err = await require_ctx(sid, allowed_phases=("day", "vote", "idle"))
        if err:
            return err

        sess = await sio.get_session(sid, namespace="/room")
        if sess.get("spectator"):
            return {"ok": True, "state": {}, "blocked": {}}

        r = ctx.r
        state, blocked = await get_user_state_and_block(r, ctx.rid, ctx.uid)
        return {"ok": True, "state": state, "blocked": blocked}

    except Exception:
        log.exception("sio.self_state.error", sid=sid)
        return {"ok": False}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:screen:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def screen(sid, data) -> ScreenAck:
    try:
        sess = await sio.get_session(sid, namespace="/room")
        actor_uid = int(sess["uid"])
        actor_user_name = str(sess.get("username") or f"user{actor_uid}")
        actor_role = None

        rid = int(sess.get("rid") or 0)
        if not rid:
            return {"ok": False, "error": "no_room", "status": 400}

        r = get_redis()
        want_on = bool((data or {}).get("on"))
        target = int((data or {}).get("target") or actor_uid)

        if want_on and not get_cached_settings().streams_can_start:
            return {"ok": False, "error": "streams_start_disabled", "status": 403}

        if not await r.sismember(f"room:{rid}:members", str(target)):
            return {"ok": False, "error": "not_in_room", "status": 403}

        if target != actor_uid:
            role_in_room = await r.hget(f"room:{rid}:user:{actor_uid}:info", "role")
            actor_role = str(role_in_room or sess.get("role") or "user")
            trg_role = str(await r.hget(f"room:{rid}:user:{target}:info", "role") or "user")
            err = ensure_can_act_role(actor_role, trg_role)
            if err:
                return err

        if want_on and target == actor_uid:
            bl = await r.hget(f"room:{rid}:user:{actor_uid}:block", "screen")
            if (bl or "0") == "1":
                return {"ok": False, "error": "blocked", "status": 403}

        if want_on:
            ok, owner = await claim_screen(r, rid, target)
            if not ok and owner and owner != target:
                return {"ok": False, "error": "busy", "status": 409, "owner": owner}

            await sio.emit("screen_owner",
                           {"user_id": target},
                           room=f"room:{rid}",
                           namespace="/room")
            await sio.emit("rooms_stream",
                           {"id": rid, "owner": target},
                           namespace="/rooms")
            await r.set(f"room:{rid}:screen_started_at", str(int(time())), nx=True, ex=86400)
            try:
                try:
                    target_username = await r.hget(f"room:{rid}:user:{target}:info", "username")
                except Exception:
                    target_username = None
                details = f"Старт стрима room_id={rid} target_user={target}"
                if target_username:
                    details += f" target_username={target_username}"
                if actor_uid != target:
                    details += f" actor_user={actor_uid}"
                    if actor_user_name:
                        details += f" actor_username={actor_user_name}"
                    if actor_role:
                        details += f" actor_role={actor_role}"
                async with SessionLocal() as s:
                    await log_action(
                        s,
                        user_id=actor_uid,
                        username=actor_user_name,
                        action="stream_start",
                        details=details,
                    )
            except Exception:
                log.exception("sio.stream_start.log_failed", rid=rid, uid=actor_uid, target=target)
            return {"ok": True, "on": True}

        canceled = bool((data or {}).get("canceled"))
        await stop_screen_for_user(r, rid, target, canceled=canceled, actor_uid=actor_uid, actor_username=actor_user_name, actor_role=actor_role)

        return {"ok": True, "on": False}

    except Exception:
        log.exception("sio.screen.error", sid=sid)
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:moderate:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def moderate(sid, data) -> ModerateAck:
    try:
        sess = await sio.get_session(sid, namespace="/room")
        actor_uid = int(sess["uid"])
        actor_user_name = str(sess.get("username") or f"user{actor_uid}")
        rid = int(sess.get("rid") or 0)
        if not rid:
            log.warning("sio.moderate.no_room", actor_uid=actor_uid)
            return {"ok": False, "error": "no_room", "status": 400}

        target = int((data or {}).get("user_id") or 0)
        blocks = (data or {}).get("blocks") or {}
        if not target or not isinstance(blocks, dict):
            log.warning("sio.moderate.bad_request", actor_uid=actor_uid, rid=rid)
            return {"ok": False, "error": "bad_request", "status": 400}

        norm = {k: blocks[k] for k in KEYS_BLOCK if k in blocks}
        if not norm:
            log.warning("sio.moderate.no_changes", actor_uid=actor_uid, rid=rid)
            return {"ok": False, "error": "no_changes", "status": 400}

        r = get_redis()
        role_in_room = await r.hget(f"room:{rid}:user:{actor_uid}:info", "role")
        base_actor_role = str(role_in_room or sess.get("role") or "user")
        trg_role = str(await r.hget(f"room:{rid}:user:{target}:info", "role") or "user")
        raw_gstate = await r.hgetall(f"room:{rid}:game_state")
        phase = str(raw_gstate.get("phase") or "idle")
        actor_role = base_actor_role
        if phase != "idle":
            try:
                head_uid = int(raw_gstate.get("head") or 0)
            except Exception:
                head_uid = 0

            if actor_uid != head_uid:
                return {"ok": False, "error": "forbidden", "status": 403}

            actor_role = "head"

        if actor_role != "head" and actor_role == trg_role:
            return {"ok": False, "error": "forbidden", "status": 403}

        applied, forced_off = await apply_blocks_and_emit(r, rid, actor_uid=actor_uid, actor_role=actor_role, target_uid=target, changes_bool=norm)

        if "__error__" in forced_off:
            err = forced_off["__error__"]
            return {"ok": False, "error": err, "status": 403}

        if applied.get("screen") == "1":
            await stop_screen_for_user(r, rid, target, actor_uid=actor_uid, actor_username=actor_user_name, actor_role=actor_role)

        if applied or forced_off:
            try:
                target_username = await r.hget(f"room:{rid}:user:{target}:info", "username")
            except Exception:
                target_username = None
            details = f"Блокировка в комнате room_id={rid} target_user={target}"
            if target_username:
                details += f" target_username={target_username}"
            if actor_user_name:
                details += f" actor_username={actor_user_name}"
            details += f" actor_role={actor_role} applied={applied}"
            async with SessionLocal() as s:
                await log_action(
                    s,
                    user_id=actor_uid,
                    username=actor_user_name,
                    action="room_blocks",
                    details=details,
                )

        return {"ok": True, "applied": applied, "forced_off": forced_off}

    except Exception:
        log.exception("sio.moderate.error", sid=sid)
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:kick:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def kick(sid, data):
    try:
        sess = await sio.get_session(sid, namespace="/room")
        actor_uid = int(sess["uid"])
        actor_user_name = str(sess.get("username") or f"user{actor_uid}")
        rid = int(sess.get("rid") or 0)
        if not rid:
            return {"ok": False, "error": "no_room", "status": 400}

        target = int((data or {}).get("user_id") or 0)
        if not target:
            return {"ok": False, "error": "bad_request", "status": 400}

        r = get_redis()
        if not await r.sismember(f"room:{rid}:members", str(target)):
            return {"ok": False, "error": "user_not_in_room", "status": 404}

        role_in_room = await r.hget(f"room:{rid}:user:{actor_uid}:info", "role")
        actor_role = str(role_in_room or sess.get("role") or "user")
        trg_role = str(await r.hget(f"room:{rid}:user:{target}:info", "role") or "user")
        err = ensure_can_act_role(actor_role, trg_role)
        if err:
            return err

        await sio.emit("force_leave",
                       {"room_id": rid,
                        "reason": "room_kick",
                        "by": {"user_id": actor_uid, "role": actor_role}},
                       room=f"user:{target}",
                       namespace="/room")

        await stop_screen_for_user(r, rid, target, actor_uid=actor_uid, actor_username=actor_user_name, actor_role=actor_role)

        occ, _, pos_updates = await leave_room_atomic(r, rid, target)
        try:
            await r.srem(f"room:{rid}:ready", str(target))
        except Exception as e:
            log.warning("sio.kick.ready_delete_failed", rid=rid, target_uid=target, err=type(e).__name__)
        try:
            await r.delete(f"room:{rid}:user:{target}:epoch")
        except Exception as e:
            log.warning("sio.kick.epoch_delete_failed", rid=rid, target_uid=target, err=type(e).__name__)

        await sio.emit("member_left",
                       {"user_id": target},
                       room=f"room:{rid}",
                       namespace="/room")
        if pos_updates:
            await sio.emit("positions",
                           {"updates": [{"user_id": u, "position": p} for u, p in pos_updates]},
                           room=f"room:{rid}",
                           namespace="/room")

        await emit_rooms_occupancy_safe(r, rid, occ)

        try:
            target_username = await r.hget(f"room:{rid}:user:{target}:info", "username")
        except Exception:
            target_username = None
        details = f"Кик из комнаты room_id={rid} target_user={target}"
        if target_username:
            details += f" target_username={target_username}"
        if actor_user_name:
            details += f" actor_username={actor_user_name}"
        details += f" actor_role={actor_role}"
        async with SessionLocal() as s:
            await log_action(
                s,
                user_id=actor_uid,
                username=actor_user_name,
                action="room_kick",
                details=details,
            )

        return {"ok": True}

    except Exception:
        log.exception("sio.kick.error", sid=sid)
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_leave:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_leave(sid, data):
    try:
        sess = await sio.get_session(sid, namespace="/room")
        ctx, err = await require_ctx(sid, allowed_phases=("day", "vote", "idle"))
        if err:
            return err

        uid = ctx.uid
        rid = ctx.rid
        r = ctx.r
        raw_gstate = ctx.gstate
        phase = ctx.phase
        if phase == "idle":
            return {"ok": False, "error": "no_game", "status": 400}

        head_uid = ctx.head_uid
        is_player = await r.sismember(f"room:{rid}:game_players", str(uid))
        if not is_player:
            return {"ok": False, "error": "not_player", "status": 400}

        was_alive = await r.sismember(f"room:{rid}:game_alive", str(uid))
        if not was_alive:
            return {"ok": False, "error": "already_dead", "status": 400}

        handled_by_predefined_farewell = False
        if phase == "day":
            current_uid = ctx.gint("day_current_uid")
            pre_active = ctx.gbool("day_prelude_active")
            pre_uid = ctx.gint("day_prelude_uid")
            if current_uid == uid:
                try:
                    if pre_active and pre_uid and pre_uid == uid:
                        payload = await finish_day_prelude_speech(r, rid, raw_gstate, uid)
                        handled_by_predefined_farewell = True
                    else:
                        payload = await finish_day_speech(r, rid, raw_gstate, uid)
                    await sio.emit("game_day_speech",
                                   payload,
                                   room=f"room:{rid}",
                                   namespace="/room")
                except Exception:
                    log.exception("sio.game_leave.finish_speech_failed", rid=rid, uid=uid)

        if phase == "vote":
            vote_speaker_uid = ctx.gint("vote_speech_uid")
            vote_kind = ctx.gstr("vote_speech_kind")
            vote_results_ready = ctx.gbool("vote_results_ready")
            leaders = ctx.gcsv_ints("vote_leaders_order")
            if vote_results_ready and not vote_speaker_uid and len(leaders) == 1 and leaders[0] == uid:
                removed = await process_player_death(r, rid, uid, head_uid=head_uid, phase_override=phase, reason="vote")
                if removed:
                    async with r.pipeline() as p:
                        await p.hset(
                            f"room:{rid}:game_state",
                            mapping={
                                "vote_done": "1",
                                "vote_started": "0",
                                "vote_aborted": "1",
                                "vote_results_ready": "0",
                                "vote_speeches_done": "1",
                                "vote_prev_leaders": "",
                                "vote_lift_state": "",
                                "vote_leaders_order": "",
                                "vote_leader_idx": "0",
                                "vote_speech_uid": "0",
                                "vote_speech_started": "0",
                                "vote_speech_duration": "0",
                                "vote_speech_kind": "",
                                "vote_current_uid": "0",
                            },
                        )
                        await p.delete(
                            f"room:{rid}:game_nominees",
                            f"room:{rid}:game_nom_speakers",
                            f"room:{rid}:game_votes",
                        )
                        await p.execute()

                    await sio.emit("game_vote_aborted",
                                   {"room_id": rid,
                                    "blocked": False,
                                    "reason": "leader_suicide",
                                    "nominees": []},
                                   room=f"room:{rid}",
                                   namespace="/room")

                return {"ok": True, "status": 200, "room_id": rid}

            if vote_speaker_uid == uid:
                try:
                    payload = await finish_vote_speech(r, rid, raw_gstate, uid)
                    await sio.emit("game_day_speech",
                                   payload,
                                   room=f"room:{rid}",
                                   namespace="/room")
                except Exception:
                    log.exception("sio.game_leave.finish_vote_speech_failed", rid=rid, uid=uid)

                if vote_kind == "farewell":
                    handled_by_predefined_farewell = True

        if handled_by_predefined_farewell:
            return {"ok": True, "status": 200, "room_id": rid}

        removed = await process_player_death(r, rid, uid, head_uid=head_uid, phase_override=phase, reason="suicide")
        if removed:
            block_now, block_next, _ = await decide_vote_blocks_on_death(r, rid, raw_gstate, uid)
            if block_now:
                await block_vote_and_clear(r, rid, reason="suicide", phase=phase)
            if block_next:
                try:
                    await r.hset(f"room:{rid}:game_state", mapping={"vote_blocked_next": "1"})
                except Exception:
                    log.exception("sio.game_leave.mark_vote_blocked_next_failed", rid=rid)
            if phase in ("roles_pick", "mafia_talk_start", "mafia_talk_end"):
                try:
                    await perform_game_end(ctx, sess, confirm=True, allow_non_head=True, reason="early_leave_before_day")
                except Exception:
                    log.exception("sio.game_leave.auto_game_end_failed", rid=rid, uid=uid)

        return {"ok": True, "status": 200, "room_id": rid}

    except Exception:
        log.exception("sio.game_leave.error", sid=sid)
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_start:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_start(sid, data) -> GameStartAck:
    try:
        data = data or {}
        confirm = bool(data.get("confirm"))
        sess = await sio.get_session(sid, namespace="/room")
        ctx, err = await require_ctx(sid)
        if err:
            return err

        uid = ctx.uid
        rid = ctx.rid
        r = ctx.r
        params = await r.hgetall(f"room:{rid}:params")
        if not params:
            return {"ok": False, "error": "room_not_found", "status": 404}

        cur_phase = ctx.phase
        if cur_phase != "idle":
            return {"ok": False, "error": "already_started", "status": 409}

        if not await r.sismember(f"room:{rid}:members", str(uid)):
            return {"ok": False, "error": "not_in_room", "status": 403}

        app_settings = get_cached_settings()
        if not app_settings.games_can_start:
            return {"ok": False, "error": "game_start_disabled", "status": 403}

        min_ready = app_settings.game_min_ready_players
        members = await r.smembers(f"room:{rid}:members")
        members = members or set()
        ready_ids = await r.smembers(f"room:{rid}:ready")
        ready_ids = ready_ids or set()
        not_ready_raw = [mid for mid in members if mid not in ready_ids]
        ready_cnt = len(ready_ids)
        if ready_cnt != min_ready or len(not_ready_raw) != 1:
            return {"ok": False, "error": "not_enough_ready", "status": 400}

        try:
            head_uid = int(not_ready_raw[0])
        except Exception:
            return {"ok": False, "error": "not_enough_ready", "status": 400}

        if uid != head_uid:
            return {"ok": False, "error": "forbidden", "status": 403}

        member_ids: set[int] = set()
        for mid in members or []:
            try:
                member_ids.add(int(mid))
            except Exception:
                continue
        if member_ids:
            async with SessionLocal() as s:
                suspended_ids = await fetch_active_users_by_kind(s, member_ids, SANCTION_SUSPEND)
            if suspended_ids:
                return {
                    "ok": False,
                    "status": 409,
                    "error": "suspend_present",
                    "blocking_users": sorted(suspended_ids),
                }

        streaming_owner_raw = await r.get(f"room:{rid}:screen_owner")
        streaming_owner = int(streaming_owner_raw) if streaming_owner_raw else 0
        blocking_users: list[int] = []
        members_for_block_check = await r.smembers(f"room:{rid}:members")
        if members_for_block_check:
            async with r.pipeline() as p:
                for pid in members_for_block_check:
                    await p.hmget(f"room:{rid}:user:{pid}:block", *KEYS_BLOCK)
                rows = await p.execute()
            for pid, row in zip(members_for_block_check, rows):
                if any((v or "0") == "1" for v in (row or [])):
                    try:
                        blocking_users.append(int(pid))
                    except Exception:
                        continue

        if streaming_owner or blocking_users:
            return {
                "ok": False,
                "status": 409,
                "error": "streaming_present" if streaming_owner else "blocked_params",
                "room_id": rid,
                "streaming_owner": streaming_owner,
                "blocking_users": blocking_users
            }

        participant_ids: set[int] = {head_uid}
        for x in (ready_ids or []):
            try:
                participant_ids.add(int(x))
            except Exception:
                continue

        off_speakers: list[int] = []
        off_visibility: list[int] = []
        if participant_ids:
            async with r.pipeline() as p:
                for pid in participant_ids:
                    await p.hmget(f"room:{rid}:user:{pid}:state", "speakers", "visibility")
                rows = await p.execute()

            for pid, row in zip(participant_ids, rows):
                if not row:
                    continue
                sp = row[0] if len(row) > 0 else None
                vis = row[1] if len(row) > 1 else None
                if sp == "0" or sp == b"0":
                    off_speakers.append(pid)
                if vis == "0" or vis == b"0":
                    off_visibility.append(pid)
        if off_speakers or off_visibility:
            return {
                "ok": False,
                "status": 409,
                "error": "media_off",
                "room_id": rid,
                "off_speakers": off_speakers,
                "off_visibility": off_visibility,
            }

        conflict_users: set[int] = set()
        participants = participant_ids
        other_ids = [int(x) for x in (await r.zrange("rooms:index", 0, -1) or []) if int(x) != rid]
        if other_ids:
            async with r.pipeline() as p:
                for other in other_ids:
                    await p.hgetall(f"room:{other}:game_state")
                    await p.smembers(f"room:{other}:game_alive")
                rows = await p.execute()

            idx = 0
            for _ in other_ids:
                raw_state = rows[idx] or {}
                raw_alive = rows[idx + 1] or []
                idx += 2
                phase_other = str(raw_state.get("phase") or "idle")
                if phase_other == "idle":
                    continue

                try:
                    head_other = int(raw_state.get("head") or 0)
                except Exception:
                    head_other = 0

                if head_other in participants:
                    conflict_users.add(head_other)
                for v in raw_alive:
                    try:
                        u = int(v)
                    except Exception:
                        continue
                    if u in participants:
                        conflict_users.add(u)

                if conflict_users:
                    break

        if conflict_users:
            return {"ok": False, "status": 409, "error": "already_in_other_game", "room_id": rid, "conflict_users": list(conflict_users)}

        if not confirm:
            return {"ok": True, "status": 200, "room_id": rid, "can_start": True, "min_ready": min_ready}

        try:
            raw_game = await r.hgetall(f"room:{rid}:game")
        except Exception:
            raw_game = {}
        wink_knock = game_flag(raw_game, "wink_knock", True)
        try:
            winks_limit = int(app_settings.winks_limit)
        except Exception:
            winks_limit = 0
        try:
            knocks_limit = int(app_settings.knocks_limit)
        except Exception:
            knocks_limit = 0
        if winks_limit < 0:
            winks_limit = 0
        if knocks_limit < 0:
            knocks_limit = 0
        if not wink_knock:
            winks_limit = 0
            knocks_limit = 0

        try:
            await sio.emit("game_starting",
                           {"room_id": rid, "delay_ms": 1000},
                           room=f"room:{rid}",
                           namespace="/room")
        except Exception:
            log.exception("sio.game_start.game_starting_emit_failed", rid=rid)

        await asyncio.sleep(0.5)

        player_ids = [str(x) for x in ready_ids if str(x) != str(head_uid)]
        random.shuffle(player_ids)
        seats: dict[str, int] = {}
        slot = 1
        for pid in player_ids:
            seats[pid] = slot
            slot += 1
        seats[str(head_uid)] = 11
        now_ts = int(time())
        bgm_seed = random.randint(1, 2**31 - 1)
        async with r.pipeline() as p:
            await p.hset(f"room:{rid}:game_state",
                         mapping={
                             "phase": "roles_pick",
                             "started_at": str(now_ts),
                             "bgm_seed": str(bgm_seed),
                             "started_by": str(uid),
                             "head": str(head_uid),
                             "game_finished": "0",
                             "game_result": "",
                             "draw_base_day": "0",
                             "draw_base_alive": "0",
                             "vote_blocked": "0",
                             "vote_blocked_next": "0",
                             "best_move_uid": "0",
                             "best_move_active": "0",
                             "best_move_targets": "",
                         })
            if seats:
                await p.hset(f"room:{rid}:game_seats", mapping={k: str(v) for k, v in seats.items()})

            if player_ids:
                await p.delete(
                    f"room:{rid}:game_players",
                    f"room:{rid}:game_alive",
                    f"room:{rid}:game_fouls",
                    f"room:{rid}:game_deaths",
                    f"room:{rid}:game_short_speech_used",
                    f"room:{rid}:game_nominees",
                    f"room:{rid}:game_nom_speakers",
                    f"room:{rid}:game_votes",
                    f"room:{rid}:game_actions",
                    f"room:{rid}:game_votes_last",
                    f"room:{rid}:game_checked:don",
                    f"room:{rid}:game_checked:sheriff",
                    f"room:{rid}:game_farewell_wills",
                    f"room:{rid}:game_farewell_limits",
                    f"room:{rid}:game_winks_left",
                    f"room:{rid}:game_knocks_left",
                )
                await p.sadd(f"room:{rid}:game_players", *player_ids)
                await p.sadd(f"room:{rid}:game_alive", *player_ids)
                await p.hset(f"room:{rid}:game_winks_left", mapping={pid: str(winks_limit) for pid in player_ids})
                await p.hset(f"room:{rid}:game_knocks_left", mapping={pid: str(knocks_limit) for pid in player_ids})
            await p.delete(f"room:{rid}:ready")
            await p.execute()

        await init_roles_deck(r, rid)

        if player_ids and head_uid:
            for pid in player_ids:
                try:
                    target_uid = int(pid)
                except Exception:
                    continue
                try:
                    await apply_blocks_and_emit(r, rid, actor_uid=head_uid, actor_role="head", target_uid=target_uid, changes_bool={"mic": True, "visibility": True})
                except Exception:
                    log.exception("sio.game_start.autoblock_failed", rid=rid, head=head_uid, target=pid)
                    continue

        payload: GameStartAck = {
            "ok": True,
            "status": 200,
            "room_id": rid,
            "phase": "roles_pick",
            "min_ready": min_ready,
            "seats": {k: int(v) for k, v in seats.items()},
            "bgm_seed": bgm_seed,
            "wink_knock": wink_knock,
            "winks_limit": winks_limit,
            "knocks_limit": knocks_limit,
        }

        await sio.emit("game_started",
                       payload,
                       room=f"room:{rid}",
                       namespace="/room")

        alive_cnt = len(player_ids)
        await sio.emit("rooms_occupancy",
                       {"id": rid, "occupancy": alive_cnt},
                       namespace="/rooms")

        try:
            briefs = await get_rooms_brief(r, [rid])
            if briefs:
                await sio.emit("rooms_upsert",
                               briefs[0],
                               namespace="/rooms")
        except Exception:
            log.exception("sio.game_start.rooms_upsert_failed", rid=rid)

        try:
            async with SessionLocal() as s:
                await log_action(
                    s,
                    user_id=uid,
                    username=str(sess.get("username") or f"user{uid}"),
                    action="game_start",
                    details=f"Запуск игры room_id={rid}",
                )
        except Exception:
            log.exception("sio.game_start.log_failed", rid=rid, uid=uid)

        await advance_roles_turn(r, rid, auto=False)

        return payload

    except Exception:
        log.exception("sio.game_start.error", sid=sid)
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_roles_pick:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_roles_pick(sid, data) -> GameRolePickAck:
    try:
        data = data or {}
        ctx, err = await require_ctx(sid, allowed_phases="roles_pick")
        if err:
            return err

        uid = ctx.uid
        rid = ctx.rid
        r = ctx.r
        phase = ctx.phase
        if phase != "roles_pick":
            return {"ok": False, "error": "bad_phase", "status": 400}

        turn_uid = ctx.gint("roles_turn_uid")
        if uid != turn_uid:
            return {"ok": False, "error": "not_your_turn", "status": 403}

        is_player = await r.sismember(f"room:{rid}:game_players", str(uid))
        head_uid = ctx.head_uid
        if not is_player and uid != head_uid:
            return {"ok": False, "error": "not_player", "status": 403}

        card = int(data.get("card") or 0)
        if card <= 0:
            return {"ok": False, "error": "bad_card", "status": 400}

        ok, role, err = await assign_role_for_user(r, rid, uid, card_index=card)
        if not ok or role is None:
            status = 400
            if err in ("bad_card", "card_taken", "already_has_role"):
                status = 409
            error_msg = err if err is not None else "failed"
            return {"ok": False, "error": error_msg, "status": status}

        await sio.emit("game_role_assigned",
                       {"room_id": rid,
                        "user_id": uid,
                        "role": role,
                        "card": card},
                       room=f"user:{uid}",
                       namespace="/room")

        await sio.emit("game_roles_picked",
                       {"room_id": rid,
                        "user_id": uid},
                       room=f"room:{rid}",
                       namespace="/room")

        await advance_roles_turn(r, rid, auto=False)

        return {"ok": True, "status": 200, "room_id": rid, "role": role}

    except Exception:
        log.exception("sio.game_roles_pick.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_phase_next:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_phase_next(sid, data):
    try:
        data = data or {}
        want_from = str(data.get("from") or "")
        want_to = str(data.get("to") or "")
        ctx, err = await require_ctx(sid)
        if err:
            return err

        uid = ctx.uid
        rid = ctx.rid
        r = ctx.r
        raw_gstate = ctx.gstate
        cur_phase = ctx.phase
        if cur_phase == "idle":
            return {"ok": False, "error": "no_game", "status": 400}

        head_uid = ctx.head_uid
        if not head_uid or uid != head_uid:
            return {"ok": False, "error": "forbidden", "status": 403}

        if want_from and want_from != cur_phase:
            return {"ok": False, "error": "bad_phase_from", "status": 400}

        if cur_phase == "roles_pick" and want_to == "mafia_talk_start":
            roles_done = str(raw_gstate.get("roles_done") or "0") == "1"
            if not roles_done:
                return {"ok": False, "error": "roles_not_done", "status": 400}

            raw_roles = await r.hgetall(f"room:{rid}:game_roles")
            roles_map: dict[int, str] = {}
            for k, v in (raw_roles or {}).items():
                try:
                    uid_i = int(k)
                except Exception:
                    continue
                if v is None:
                    continue
                roles_map[uid_i] = str(v)

            mafia_targets = [u for u, role in roles_map.items() if role in ("mafia", "don")]

            for target_uid in mafia_targets:
                try:
                    await apply_blocks_and_emit(r, rid, actor_uid=head_uid, actor_role="head", target_uid=target_uid, changes_bool={"visibility": False}, phase_override="mafia_talk_start")
                except Exception:
                    log.exception("sio.game_phase_next.mafia_unblock_failed", rid=rid, head=head_uid, target=target_uid)
                    continue

            if mafia_targets:
                async with r.pipeline() as p:
                    for target_uid in mafia_targets:
                        await p.hset(f"room:{rid}:user:{target_uid}:state", mapping={"visibility": "1"})
                    await p.execute()

                for target_uid in mafia_targets:
                    await emit_state_changed_filtered(r, rid, target_uid, {"visibility": "1"}, phase_override="mafia_talk_start")

            now_ts = int(time())
            duration = get_cached_settings().mafia_talk_seconds
            async with r.pipeline() as p:
                await p.hset(
                    f"room:{rid}:game_state",
                    mapping={
                        "phase": "mafia_talk_start",
                        "mafia_talk_started": str(now_ts),
                        "mafia_talk_duration": str(duration),
                    },
                )
                await p.execute()

            remaining = duration
            payload = {
                "ok": True,
                "status": 200,
                "room_id": rid,
                "from": cur_phase,
                "to": "mafia_talk_start",
                "mafia_talk_start": {"deadline": remaining},
            }

            await sio.emit("game_phase_change",
                           {"room_id": rid,
                            "from": cur_phase,
                            "to": "mafia_talk_start",
                            "mafia_talk_start": {"deadline": remaining}},
                           room=f"room:{rid}",
                           namespace="/room")

            return payload

        if cur_phase == "mafia_talk_start" and want_to == "mafia_talk_end":
            raw_roles = await r.hgetall(f"room:{rid}:game_roles")
            roles_map: dict[int, str] = {}
            for k, v in (raw_roles or {}).items():
                try:
                    uid_i = int(k)
                except Exception:
                    continue
                if v is None:
                    continue
                roles_map[uid_i] = str(v)

            mafia_targets = [u for u, role in roles_map.items() if role in ("mafia", "don")]

            if mafia_targets:
                async with r.pipeline() as p:
                    for target_uid in mafia_targets:
                        await p.hset(f"room:{rid}:user:{target_uid}:state", mapping={"visibility": "0"})
                    await p.execute()

                for target_uid in mafia_targets:
                    await emit_state_changed_filtered(r, rid, target_uid, {"visibility": "0"})

            for target_uid in mafia_targets:
                try:
                    applied, forced_off = await apply_blocks_and_emit(r, rid, actor_uid=head_uid, actor_role="head", target_uid=target_uid, changes_bool={"visibility": True})
                except Exception:
                    log.exception("sio.game_phase_next.mafia_reblock_failed", rid=rid, head=head_uid, target=target_uid)
                    continue

                if "__error__" in forced_off:
                    continue

            async with r.pipeline() as p:
                await p.hset(f"room:{rid}:game_state", mapping={"phase": "mafia_talk_end"})
                await p.hdel(f"room:{rid}:game_state", "mafia_talk_started", "mafia_talk_duration")
                await p.execute()

            payload = {
                "ok": True,
                "status": 200,
                "room_id": rid,
                "from": cur_phase,
                "to": "mafia_talk_end",
            }

            await sio.emit("game_phase_change",
                           {"room_id": rid,
                            "from": cur_phase,
                            "to": "mafia_talk_end"},
                           room=f"room:{rid}",
                           namespace="/room")

            return payload

        if cur_phase == "mafia_talk_end" and want_to == "day":
            day_number = ctx.gint("day_number")
            last_opening_uid = ctx.gint("day_last_opening_uid")
            opening_uid, closing_uid, alive_order = await compute_day_opening_and_closing(r, rid, last_opening_uid)
            new_day_number = day_number + 1 if opening_uid else day_number
            vote_blocked_next = str(raw_gstate.get("vote_blocked_next") or "0") == "1"
            vote_blocked_val = "1" if vote_blocked_next else "0"
            alive_raw = await r.smembers(f"room:{rid}:game_alive")
            alive_ids: list[int] = []
            for v in (alive_raw or []):
                try:
                    alive_ids.append(int(v))
                except Exception:
                    continue

            if alive_ids and head_uid:
                for target_uid in alive_ids:
                    try:
                        await apply_blocks_and_emit(r, rid, actor_uid=head_uid, actor_role="head", target_uid=target_uid, changes_bool={"visibility": False})
                    except Exception:
                        log.exception("sio.game_phase_next.day_unblock_visibility_failed", rid=rid, head=head_uid, target=target_uid)
                        continue

                async with r.pipeline() as p:
                    for target_uid in alive_ids:
                        await p.hset(f"room:{rid}:user:{target_uid}:state", mapping={"visibility": "1"})
                    await p.execute()

                for target_uid in alive_ids:
                    await emit_state_changed_filtered(r, rid, target_uid, {"visibility": "1"})

            mapping = {
                "phase": "day",
                "day_number": str(new_day_number),
                "day_opening_uid": str(opening_uid or 0),
                "day_closing_uid": str(closing_uid or 0),
                "day_current_uid": "0",
                "day_speech_started": "0",
                "day_speech_duration": "0",
                "day_speeches_done": "0",
                "vote_blocked": vote_blocked_val,
                "vote_blocked_next": "0",
            }
            async with r.pipeline() as p:
                await p.hset(f"room:{rid}:game_state", mapping=mapping)
                await p.delete(
                    f"room:{rid}:game_nominees",
                    f"room:{rid}:game_nom_speakers",
                )
                if vote_blocked_next:
                    await p.delete(f"room:{rid}:game_votes")
                await p.execute()

            payload = {
                "ok": True,
                "status": 200,
                "room_id": rid,
                "from": cur_phase,
                "to": "day",
                "day": {
                    "number": new_day_number,
                    "opening_uid": opening_uid,
                    "closing_uid": closing_uid,
                    "vote_blocked": vote_blocked_next,
                },
            }

            await sio.emit("game_phase_change",
                           {"room_id": rid,
                            "from": cur_phase,
                            "to": "day",
                            "day": {"number": new_day_number,
                                    "opening_uid": opening_uid,
                                    "closing_uid": closing_uid,
                                    "vote_blocked": vote_blocked_next}},
                           room=f"room:{rid}",
                           namespace="/room")

            return payload

        if cur_phase == "day" and want_to == "vote":
            if str(raw_gstate.get("vote_blocked") or "0") == "1":
                return {"ok": False, "error": "vote_blocked", "status": 409}

            speeches_done = str(raw_gstate.get("day_speeches_done") or "0") == "1"
            if not speeches_done:
                return {"ok": False, "error": "speeches_not_done", "status": 400}

            ordered = await get_nominees_in_order(r, rid)
            if not ordered:
                return {"ok": False, "error": "no_nominees", "status": 409}

            first_uid = ordered[0]
            vote_duration = get_positive_setting_int("VOTE_SECONDS", 3)
            async with r.pipeline() as p:
                await p.hset(
                    f"room:{rid}:game_state",
                    mapping={
                        "phase": "vote",
                        "vote_current_uid": str(first_uid or 0),
                        "vote_started": "0",
                        "vote_duration": str(vote_duration),
                        "vote_done": "0",
                        "vote_results_ready": "0",
                        "vote_speeches_done": "0",
                        "vote_prev_leaders": "",
                        "vote_lift_state": "",
                        "vote_blocked": "0",
                        "vote_blocked_next": "0",
                    },
                )
                await p.delete(f"room:{rid}:game_votes")
                await p.execute()

            payload = {
                "ok": True,
                "status": 200,
                "room_id": rid,
                "from": cur_phase,
                "to": "vote",
                "vote": {
                    "nominees": ordered,
                    "current_uid": first_uid,
                    "deadline": 0,
                    "done": False,
                },
            }

            await sio.emit("game_phase_change",
                           {"room_id": rid,
                            "from": cur_phase,
                            "to": "vote",
                            "vote": {"nominees": ordered,
                                     "current_uid": first_uid,
                                     "deadline": 0,
                                     "done": False}},
                           room=f"room:{rid}",
                           namespace="/room")

            return payload

        if cur_phase == "day" and want_to == "night":
            speeches_done = str(raw_gstate.get("day_speeches_done") or "0") == "1"
            if not speeches_done:
                return {"ok": False, "error": "speeches_not_done", "status": 400}

            draw_base_day = ctx.gint("draw_base_day")
            draw_mapping: dict[str, str] = {}
            if draw_base_day <= 0:
                try:
                    alive_cnt = int(await r.scard(f"room:{rid}:game_alive") or 0)
                except Exception:
                    alive_cnt = 0
                draw_mapping = {"draw_base_day": str(ctx.gint("day_number")),
                                "draw_base_alive": str(alive_cnt)}

            bgm_seed = random.randint(1, 2**31 - 1)
            async with r.pipeline() as p:
                mapping = build_night_reset_mapping(include_vote_meta=True)
                mapping["bgm_seed"] = str(bgm_seed)
                if draw_mapping:
                    mapping.update(draw_mapping)
                await p.hset(f"room:{rid}:game_state", mapping=mapping)
                await p.delete(f"room:{rid}:night_shots", f"room:{rid}:night_checks")
                await p.execute()

            await apply_night_start_blocks(r, rid, head_uid=head_uid, emit_safe=True)

            await sio.emit("game_phase_change",
                           {"room_id": rid,
                            "from": cur_phase,
                            "to": "night",
                            "night": {"stage": "sleep", "deadline": 0},
                            "bgm_seed": bgm_seed},
                           room=f"room:{rid}",
                           namespace="/room")
            return {"ok": True, "status": 200, "room_id": rid, "from": cur_phase, "to": "night", "bgm_seed": bgm_seed}

        if cur_phase == "vote" and want_to == "night":
            vote_done = str(raw_gstate.get("vote_done") or "0") == "1"
            vote_aborted = str(raw_gstate.get("vote_aborted") or "0") == "1"
            vote_speeches_done = str(raw_gstate.get("vote_speeches_done") or "0") == "1"
            vote_results_ready = str(raw_gstate.get("vote_results_ready") or "0") == "1"

            if not vote_done:
                return {"ok": False, "error": "vote_not_done", "status": 400}

            if not vote_aborted and vote_results_ready and not vote_speeches_done:
                return {"ok": False, "error": "speeches_not_done", "status": 400}

            draw_base_day = ctx.gint("draw_base_day")
            draw_mapping: dict[str, str] = {}
            if draw_base_day <= 0:
                try:
                    alive_cnt = int(await r.scard(f"room:{rid}:game_alive") or 0)
                except Exception:
                    alive_cnt = 0
                draw_mapping = {"draw_base_day": str(ctx.gint("day_number")),
                                "draw_base_alive": str(alive_cnt)}

            bgm_seed = random.randint(1, 2**31 - 1)
            async with r.pipeline() as p:
                mapping = build_night_reset_mapping(include_vote_meta=False)
                mapping["bgm_seed"] = str(bgm_seed)
                if draw_mapping:
                    mapping.update(draw_mapping)
                await p.hset(f"room:{rid}:game_state", mapping=mapping)
                await p.delete(f"room:{rid}:night_shots", f"room:{rid}:night_checks")
                await p.execute()

            await apply_night_start_blocks(r, rid, head_uid=head_uid, emit_safe=False)

            await sio.emit("game_phase_change",
                           {"room_id": rid,
                            "from": cur_phase,
                            "to": "night",
                            "night": {"stage": "sleep", "deadline": 0},
                            "bgm_seed": bgm_seed},
                           room=f"room:{rid}",
                           namespace="/room")
            return {"ok": True, "status": 200, "room_id": rid, "from": cur_phase, "to": "night", "bgm_seed": bgm_seed}

        if cur_phase == "night" and want_to == "day":
            stage = str(raw_gstate.get("night_stage") or "sleep")
            if stage != "checks_done":
                return {"ok": False, "error": "night_not_finished", "status": 409, "night_stage": stage}

            best_move_uid = ctx.gint("best_move_uid")
            best_move_active = ctx.gbool("best_move_active")
            if best_move_uid and not best_move_active:
                return {"ok": False, "error": "best_move_required", "status": 409, "user_id": best_move_uid}

            killed_uid, ok = await compute_night_kill(r, rid)
            draw_base_day = ctx.gint("draw_base_day")
            draw_base_alive = ctx.gint("draw_base_alive")
            try:
                alive_cnt = int(await r.scard(f"room:{rid}:game_alive") or 0)
            except Exception:
                alive_cnt = 0

            draw_should_reset = bool(ok and killed_uid)
            day_number = ctx.gint("day_number")
            last_opening_uid = ctx.gint("day_last_opening_uid")
            exclude_ids = [killed_uid] if ok and killed_uid else None
            opening_uid, closing_uid, alive_order = await compute_day_opening_and_closing(r, rid, last_opening_uid, exclude_ids)
            new_day_number = day_number + 1 if opening_uid else day_number
            vote_blocked_next = str(raw_gstate.get("vote_blocked_next") or "0") == "1"
            vote_blocked_val = "1" if vote_blocked_next else "0"
            await apply_day_visibility_unblock(r, rid, head_uid=head_uid)

            mapping = {
                "phase": "day",
                "day_number": str(new_day_number),
                "day_opening_uid": str(opening_uid or 0),
                "day_closing_uid": str(closing_uid or 0),
                "day_current_uid": "0",
                "day_speech_started": "0",
                "day_speech_duration": "0",
                "day_speeches_done": "0",
                "night_kill_uid": str(killed_uid or 0),
                "night_kill_ok": "1" if ok else "0",
                "day_prelude_uid": str(killed_uid or 0),
                "day_prelude_pending": "1" if ok and killed_uid else "0",
                "day_prelude_active": "0",
                "day_prelude_done": "0",
                "night_stage": "",
                "night_shoot_started": "0",
                "night_shoot_duration": "0",
                "night_check_started": "0",
                "night_check_duration": "0",
                "vote_blocked": vote_blocked_val,
                "vote_blocked_next": "0",
            }
            if draw_should_reset:
                mapping["draw_base_day"] = "0"
                mapping["draw_base_alive"] = "0"

            async with r.pipeline() as p:
                await p.hset(f"room:{rid}:game_state", mapping=mapping)
                await p.delete(f"room:{rid}:game_nominees", f"room:{rid}:game_nom_speakers", f"room:{rid}:game_votes")
                await p.execute()

            payload = {
                "ok": True,
                "status": 200,
                "room_id": rid,
                "from": cur_phase,
                "to": "day",
                "day": {"number": new_day_number,
                        "opening_uid": opening_uid,
                        "closing_uid": closing_uid,
                        "vote_blocked": vote_blocked_next},
                "night": {"kill_uid": killed_uid or 0, "kill_ok": bool(ok)},
            }
            await sio.emit("game_phase_change",
                           {"room_id": rid,
                            "from": cur_phase,
                            "to": "day",
                            "day": payload["day"],
                            "night": payload["night"]},
                           room=f"room:{rid}",
                           namespace="/room")
            if not draw_should_reset and draw_base_day > 0 and alive_cnt == draw_base_alive and new_day_number >= draw_base_day + 3:
                try:
                    await finish_game(r, rid, result="draw", head_uid=head_uid, reason="draw")
                except Exception:
                    log.exception("sio.game_finish.draw_failed", rid=rid)

            return payload

        return {"ok": False, "error": "bad_transition", "status": 400, "from": cur_phase, "to": want_to}
    except Exception:
        log.exception("sio.game_phase_next.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_speech_next:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_speech_next(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid, allowed_phases="day", require_head=True)
        if err:
            return err

        actor_uid = ctx.uid
        rid = ctx.rid
        r = ctx.r
        raw_gstate = ctx.gstate
        phase = ctx.phase
        if phase != "day":
            return {"ok": False, "error": "bad_phase", "status": 400}

        head_uid = ctx.head_uid
        if not head_uid or actor_uid != head_uid:
            return {"ok": False, "error": "forbidden", "status": 403}

        current_uid = ctx.gint("day_current_uid")
        last_opening_uid = ctx.gint("day_last_opening_uid")
        opening_uid, closing_uid = await recompute_day_opening_and_closing_from_state(r, rid, raw_gstate)
        if not opening_uid or not closing_uid:
            opening_uid, closing_uid, alive_order = await compute_day_opening_and_closing(r, rid, last_opening_uid)
            async with r.pipeline() as p:
                await p.hset(
                    f"room:{rid}:game_state",
                    mapping={
                        "day_opening_uid": str(opening_uid or 0),
                        "day_closing_uid": str(closing_uid or 0),
                        "day_speeches_done": "0",
                    },
                )
                await p.execute()
        else:
            alive_order = await get_alive_players_in_seat_order(r, rid)
            if alive_order and opening_uid not in alive_order:
                opening_uid, closing_uid, alive_order = await compute_day_opening_and_closing(r, rid, last_opening_uid or opening_uid)
                async with r.pipeline() as p:
                    await p.hset(
                        f"room:{rid}:game_state",
                        mapping={
                            "day_opening_uid": str(opening_uid or 0),
                            "day_closing_uid": str(closing_uid or 0),
                            "day_speeches_done": "0",
                        },
                    )
                    await p.execute()

        if alive_order and opening_uid in alive_order and closing_uid not in alive_order:
            if len(alive_order) == 1:
                closing_uid = opening_uid
            else:
                idx_open = alive_order.index(opening_uid)
                closing_uid = alive_order[idx_open - 1] if idx_open > 0 else alive_order[-1]
            await r.hset(f"room:{rid}:game_state", mapping={"day_closing_uid": str(closing_uid or 0)})

        if not alive_order or not opening_uid:
            return {"ok": False, "error": "no_alive_players", "status": 400}

        next_uid: int
        is_prelude_next = False
        if not current_uid:
            pre_uid = ctx.gint("day_prelude_uid")
            pre_pending = str(raw_gstate.get("day_prelude_pending") or "0") == "1"
            if pre_uid and pre_pending:
                next_uid = pre_uid
                is_prelude_next = True
                await r.hset(f"room:{rid}:game_state",
                             mapping={
                                 "day_prelude_pending": "0",
                                 "day_prelude_active": "1",
                                 "day_prelude_done": "0"
                             })
            else:
                next_uid = opening_uid
        else:
            if current_uid == closing_uid:
                await r.hset(
                    f"room:{rid}:game_state",
                    mapping={
                        "day_last_opening_uid": str(opening_uid or 0),
                        "day_speeches_done": "1",
                    },
                )
                return {"ok": False, "error": "day_speeches_done", "status": 409}

            if current_uid not in alive_order:
                opening_uid, closing_uid, alive_order = await compute_day_opening_and_closing(r, rid, last_opening_uid or opening_uid)
                next_uid = 0
                try:
                    seat_order = await get_players_in_seat_order(r, rid)
                except Exception:
                    seat_order = []

                alive_set = set(alive_order)
                if seat_order and alive_set and current_uid in seat_order:
                    start_idx = seat_order.index(current_uid)
                    total = len(seat_order)
                    for step in range(1, total + 1):
                        cand = seat_order[(start_idx + step) % total]
                        if cand in alive_set:
                            next_uid = cand
                            break

                if not next_uid and alive_order:
                    next_uid = alive_order[0]
                if not next_uid:
                    next_uid = opening_uid

            else:
                idx = alive_order.index(current_uid)
                next_uid = alive_order[(idx + 1) % len(alive_order)]

        if (not is_prelude_next) and (next_uid not in alive_order):
            return {"ok": False, "error": "bad_next_speaker", "status": 400}

        if not is_prelude_next and current_uid and next_uid == opening_uid:
            await r.hset(
                f"room:{rid}:game_state",
                mapping={
                    "day_last_opening_uid": str(opening_uid or 0),
                    "day_speeches_done": "1",
                    "day_current_uid": "0",
                    "day_speech_started": "0",
                    "day_speech_duration": "0",
                },
            )
            payload = {
                "room_id": rid,
                "speaker_uid": 0,
                "opening_uid": opening_uid,
                "closing_uid": closing_uid,
                "deadline": 0,
                "speeches_done": True,
            }
            await sio.emit("game_day_speech",
                           payload,
                           room=f"room:{rid}",
                           namespace="/room")
            return {"ok": True, "status": 200, **payload}

        duration = get_positive_setting_int("PLAYER_TALK_SECONDS", 60)
        use_short = False
        is_prelude_active_now = is_prelude_next or (str(raw_gstate.get("day_prelude_active") or "0") == "1")
        pre_uid2 = ctx.gint("day_prelude_uid")
        if not (is_prelude_active_now and pre_uid2 and next_uid == pre_uid2):
            try:
                foul_raw = await r.hget(f"room:{rid}:game_fouls", str(next_uid))
                foul_cnt = int(foul_raw or 0)
            except Exception:
                foul_cnt = 0

            short_seconds = get_positive_setting_int("PLAYER_TALK_SHORT_SECONDS", duration)
            if foul_cnt >= 3 and short_seconds > 0:
                short_used_raw = await r.hget(f"room:{rid}:game_short_speech_used", str(next_uid))
                short_used = str(short_used_raw or "0") == "1"
                if not short_used:
                    duration = short_seconds
                    use_short = True

        now_ts = int(time())
        try:
            applied, forced_off = await apply_blocks_and_emit(r, rid, actor_uid=head_uid, actor_role="head", target_uid=next_uid, changes_bool={"mic": False})
        except Exception:
            log.exception("game_speech_next.unblock_mic_failed", rid=rid, head=head_uid, target=next_uid)
            return {"ok": False, "error": "internal", "status": 500}

        if "__error__" in forced_off:
            return {"ok": False, "error": "forbidden", "status": 403}

        try:
            await r.hset(f"room:{rid}:user:{next_uid}:state", mapping={"mic": "1"})
            await emit_state_changed_filtered(r, rid, next_uid, {"mic": "1"})
        except Exception:
            log.exception("game_speech_next.mic_state_on_failed", rid=rid, uid=next_uid)

        async with r.pipeline() as p:
            await p.hset(
                f"room:{rid}:game_state",
                mapping={
                    "day_current_uid": str(next_uid),
                    "day_speech_started": str(now_ts),
                    "day_speech_duration": str(duration),
                },
            )
            if use_short:
                await p.hset(f"room:{rid}:game_short_speech_used", str(next_uid), "1")
            await p.execute()

        remaining = duration
        farewell_section: dict[str, Any] | None = None
        if is_prelude_next:
            try:
                limit = await ensure_farewell_limit(r, rid, next_uid, mode="killed")
                wills_for = await get_farewell_wills_for(r, rid, next_uid)
                allowed = await compute_farewell_allowed(r, rid, next_uid, mode="killed")
                farewell_section = {"limit": limit, "wills": wills_for, "allowed": allowed}
            except Exception:
                log.exception("game_speech_next.farewell_build_failed", rid=rid, uid=next_uid)

        payload = {
            "room_id": rid,
            "speaker_uid": next_uid,
            "opening_uid": opening_uid,
            "closing_uid": closing_uid,
            "deadline": remaining,
            "vote_blocked": str(raw_gstate.get("vote_blocked") or "0") == "1",
        }
        if is_prelude_next:
            payload["prelude"] = True
        if farewell_section:
            payload["farewell"] = farewell_section

        await sio.emit("game_day_speech",
                       payload,
                       room=f"room:{rid}",
                       namespace="/room")

        return {"ok": True, "status": 200, **payload}
    except Exception:
        log.exception("sio.game_speech_next.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_foul:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_foul(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid, allowed_phases=("day", "vote"))
        if err:
            return err

        uid = ctx.uid
        rid = ctx.rid
        r = ctx.r
        phase = ctx.phase
        if phase not in ("day", "vote"):
            return {"ok": False, "error": "bad_phase", "status": 400}

        err = await ctx.ensure_player()
        if err:
            return err

        try:
            foul_seconds = get_cached_settings().player_foul_seconds
        except Exception:
            foul_seconds = 3

        if foul_seconds <= 0:
            foul_seconds = 3

        key_cd = f"room:{rid}:foul_cooldown:{uid}"
        if await r.exists(key_cd):
            return {"ok": False, "error": "too_soon", "status": 429}

        await r.set(key_cd, "1", ex=foul_seconds)
        until_ts = int(time()) + foul_seconds
        try:
            await r.hset(f"room:{rid}:foul_active", str(uid), str(until_ts))
            await r.expire(f"room:{rid}:foul_active", 86400)
        except Exception:
            log.warning("game_foul.active_mark_failed", rid=rid, uid=uid)

        head_uid = ctx.head_uid
        if not head_uid:
            return {"ok": False, "error": "no_head", "status": 400}

        try:
            applied, forced_off = await apply_blocks_and_emit(r, rid, actor_uid=head_uid, actor_role="head", target_uid=uid, changes_bool={"mic": False})
        except Exception:
            log.exception("game_foul.unblock_mic_failed", rid=rid, head=head_uid, target=uid)
            return {"ok": False, "error": "internal", "status": 500}

        if "__error__" in forced_off:
            return {"ok": False, "error": "forbidden", "status": 403}

        try:
            await r.hset(f"room:{rid}:user:{uid}:state", mapping={"mic": "1"})
            await emit_state_changed_filtered(r, rid, uid, {"mic": "1"})
        except Exception:
            log.exception("game_foul.mic_state_on_failed", rid=rid, uid=uid)

        duration = foul_seconds
        await sio.emit("game_foul",
                       {"room_id": rid,
                        "user_id": uid,
                        "duration": duration},
                       room=f"room:{rid}",
                       namespace="/room")

        try:
            await emit_game_fouls(r, rid)
        except Exception:
            log.exception("game_foul.emit_fouls_failed", rid=rid)

        asyncio.create_task(schedule_foul_block(rid, uid, head_uid, duration, expected_until=until_ts))

        return {"ok": True, "status": 200, "room_id": rid, "user_id": uid, "duration": duration}

    except Exception:
        log.exception("sio.game_foul.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_foul_set:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_foul_set(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid, require_head=True)
        if err:
            return err

        actor_uid = ctx.uid
        rid = ctx.rid
        target_uid = int(data.get("user_id") or 0)
        if not target_uid:
            return {"ok": False, "error": "bad_request", "status": 400}

        confirm_kill = bool(data.get("confirm_kill"))
        r = ctx.r
        raw_gstate = ctx.gstate
        phase = ctx.phase
        if phase == "idle":
            return {"ok": False, "error": "no_game", "status": 400}

        head_uid = ctx.head_uid
        if not head_uid or actor_uid != head_uid:
            return {"ok": False, "error": "forbidden", "status": 403}

        err = await ctx.ensure_player(target_uid, alive_required=False, error="not_player", status=400)
        if err:
            return err

        is_alive = await r.sismember(f"room:{rid}:game_alive", str(target_uid))
        if not is_alive:
            return {"ok": False, "error": "not_alive", "status": 404}

        try:
            foul_raw = await r.hget(f"room:{rid}:game_fouls", str(target_uid))
            foul_before = int(foul_raw or 0)
        except Exception:
            foul_before = 0

        if foul_before >= 4:
            return {"ok": False, "error": "too_many_fouls", "status": 409, "fouls": foul_before}

        if foul_before >= 3 and not confirm_kill:
            return {"ok": False, "error": "need_confirm_kill", "status": 409, "fouls": foul_before}

        try:
            foul_after = await r.hincrby(f"room:{rid}:game_fouls", str(target_uid), 1)
        except Exception:
            log.exception("game_foul_set.incr_failed", rid=rid, target=target_uid)
            return {"ok": False, "error": "internal", "status": 500}

        speech_uid = 0
        if phase == "day" and ctx.gint("day_speech_started") > 0:
            speech_uid = ctx.gint("day_current_uid")
        elif phase == "vote" and ctx.gint("vote_speech_started") > 0:
            speech_uid = ctx.gint("vote_speech_uid")
        await log_game_action(
            r,
            rid,
            {
                "type": "foul",
                "actor_id": head_uid,
                "target_id": target_uid,
                "count": int(foul_after),
                "speech_uid": speech_uid,
                "day": ctx.gint("day_number"),
            },
        )

        killed = False
        if foul_after >= 4:
            killed = True
            handled_by_predefined_farewell = False
            if phase == "day":
                current_uid = ctx.gint("day_current_uid")
                pre_active = ctx.gbool("day_prelude_active")
                pre_uid = ctx.gint("day_prelude_uid")
                if current_uid == target_uid:
                    try:
                        if pre_active and pre_uid and pre_uid == target_uid:
                            payload = await finish_day_prelude_speech(r, rid, raw_gstate, target_uid, reason_override="foul")
                            handled_by_predefined_farewell = True
                        else:
                            payload = await finish_day_speech(r, rid, raw_gstate, target_uid)
                        await sio.emit("game_day_speech",
                                       payload,
                                       room=f"room:{rid}",
                                       namespace="/room")
                    except Exception:
                        log.exception("game_foul_set.finish_speech_failed", rid=rid, uid=target_uid)

            if phase == "vote":
                vote_speaker_uid = ctx.gint("vote_speech_uid")
                vote_kind = ctx.gstr("vote_speech_kind")
                if vote_speaker_uid == target_uid:
                    try:
                        if vote_kind == "farewell":
                            payload = await finish_vote_speech(r, rid, raw_gstate, target_uid, reason_override="foul")
                            handled_by_predefined_farewell = True
                        else:
                            payload = await finish_vote_speech(r, rid, raw_gstate, target_uid)
                        await sio.emit("game_day_speech",
                                       payload,
                                       room=f"room:{rid}",
                                       namespace="/room")
                    except Exception:
                        log.exception("game_foul_set.finish_vote_speech_failed", rid=rid, uid=target_uid)

            if not handled_by_predefined_farewell:
                removed = await process_player_death(r, rid, target_uid, head_uid=head_uid, phase_override=phase, reason="foul")
                if removed:
                    block_now, block_next, _ = await decide_vote_blocks_on_death(r, rid, raw_gstate, target_uid)
                    if block_now:
                        await block_vote_and_clear(r, rid, reason="foul", phase=phase)
                    if block_next:
                        try:
                            await r.hset(f"room:{rid}:game_state", mapping={"vote_blocked_next": "1"})
                        except Exception:
                            log.exception("game_foul_set.mark_vote_blocked_next_failed", rid=rid)

        try:
            await emit_game_fouls(r, rid)
        except Exception:
            log.exception("game_foul_set.emit_fouls_failed", rid=rid)

        return {"ok": True, "status": 200, "room_id": rid, "user_id": target_uid, "fouls": foul_after, "killed": killed}

    except Exception:
        log.exception("sio.game_foul_set.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_wink:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_wink(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid)
        if err:
            return err

        uid = ctx.uid
        rid = ctx.rid
        r = ctx.r
        if ctx.phase == "idle":
            return {"ok": False, "error": "no_game", "status": 400}

        target_uid = int(data.get("user_id") or 0)
        if not target_uid:
            return {"ok": False, "error": "bad_request", "status": 400}

        if target_uid == uid:
            return {"ok": False, "error": "self_target", "status": 400}

        try:
            raw_game = await r.hgetall(f"room:{rid}:game")
        except Exception:
            raw_game = {}
        if not game_flag(raw_game, "wink_knock", True):
            return {"ok": False, "error": "feature_disabled", "status": 403}

        err = await ctx.ensure_player()
        if err:
            return err

        err = await ctx.ensure_player(target_uid, error="target_not_alive", status=404)
        if err:
            return err

        if not await r.sismember(f"room:{rid}:members", str(target_uid)):
            return {"ok": False, "error": "target_offline", "status": 404}

        try:
            left_raw = await r.hget(f"room:{rid}:game_winks_left", str(uid))
            left = int(left_raw or 0)
        except Exception:
            left = 0

        if left <= 0:
            return {"ok": False, "error": "limit_reached", "status": 409}

        try:
            left_after = int(await r.hincrby(f"room:{rid}:game_winks_left", str(uid), -1))
        except Exception:
            log.exception("game_wink.decr_failed", rid=rid, uid=uid)
            return {"ok": False, "error": "internal", "status": 500}

        if left_after < 0:
            left_after = 0
            await r.hset(f"room:{rid}:game_winks_left", str(uid), "0")

        try:
            seat_num = int(await r.hget(f"room:{rid}:game_seats", str(uid)) or 0)
        except Exception:
            seat_num = 0

        await sio.emit("game_winked",
                       {"room_id": rid, "from_seat": seat_num},
                       room=f"user:{target_uid}",
                       namespace="/room")

        return {"ok": True, "status": 200, "winks_left": left_after}

    except Exception:
        log.exception("sio.game_wink.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_knock:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_knock(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid)
        if err:
            return err

        uid = ctx.uid
        rid = ctx.rid
        r = ctx.r
        if ctx.phase == "idle":
            return {"ok": False, "error": "no_game", "status": 400}

        target_uid = int(data.get("user_id") or 0)
        if not target_uid:
            return {"ok": False, "error": "bad_request", "status": 400}

        if target_uid == uid:
            return {"ok": False, "error": "self_target", "status": 400}

        count = int(data.get("count") or 0)
        if count <= 0:
            return {"ok": False, "error": "bad_count", "status": 400}

        try:
            raw_game = await r.hgetall(f"room:{rid}:game")
        except Exception:
            raw_game = {}
        if not game_flag(raw_game, "wink_knock", True):
            return {"ok": False, "error": "feature_disabled", "status": 403}

        err = await ctx.ensure_player()
        if err:
            return err

        err = await ctx.ensure_player(target_uid, error="target_not_alive", status=404)
        if err:
            return err

        if not await r.sismember(f"room:{rid}:members", str(target_uid)):
            return {"ok": False, "error": "target_offline", "status": 404}

        raw_seats = await r.hgetall(f"room:{rid}:game_seats")
        total_seats = 0
        for v in (raw_seats or {}).values():
            try:
                seat_num = int(v or 0)
            except Exception:
                continue
            if seat_num and seat_num != 11 and seat_num > total_seats:
                total_seats = seat_num

        if total_seats <= 0:
            total_seats = get_cached_settings().game_min_ready_players

        if count > total_seats:
            return {"ok": False, "error": "bad_count", "status": 400}

        try:
            seat_actor = int(raw_seats.get(str(uid)) or 0)
        except Exception:
            seat_actor = 0
        try:
            seat_target = int(raw_seats.get(str(target_uid)) or 0)
        except Exception:
            seat_target = 0
        if not seat_actor or not seat_target:
            return {"ok": False, "error": "bad_seat", "status": 400}

        left_seat = seat_actor - 1 if seat_actor > 1 else total_seats
        right_seat = seat_actor + 1 if seat_actor < total_seats else 1
        if seat_target not in (left_seat, right_seat):
            return {"ok": False, "error": "not_neighbor", "status": 400}

        try:
            left_raw = await r.hget(f"room:{rid}:game_knocks_left", str(uid))
            left = int(left_raw or 0)
        except Exception:
            left = 0

        if left <= 0:
            return {"ok": False, "error": "limit_reached", "status": 409}

        try:
            left_after = int(await r.hincrby(f"room:{rid}:game_knocks_left", str(uid), -1))
        except Exception:
            log.exception("game_knock.decr_failed", rid=rid, uid=uid)
            return {"ok": False, "error": "internal", "status": 500}

        if left_after < 0:
            left_after = 0
            await r.hset(f"room:{rid}:game_knocks_left", str(uid), "0")

        await sio.emit("game_knocked",
                       {"room_id": rid, "from_seat": seat_actor, "count": count},
                       room=f"user:{target_uid}",
                       namespace="/room")

        return {"ok": True, "status": 200, "knocks_left": left_after}

    except Exception:
        log.exception("sio.game_knock.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_nominate:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_nominate(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid, allowed_phases="day")
        if err:
            return err

        actor_uid = ctx.uid
        rid = ctx.rid
        try:
            target_uid = int(data.get("user_id") or 0)
        except Exception:
            target_uid = 0
        if not target_uid:
            return {"ok": False, "error": "bad_request", "status": 400}

        r = ctx.r
        raw_gstate = ctx.gstate
        phase = ctx.phase
        if phase != "day":
            return {"ok": False, "error": "bad_phase", "status": 400}

        try:
            raw_game = await r.hgetall(f"room:{rid}:game")
        except Exception:
            raw_game = {}
        nominate_mode = str(raw_game.get("nominate_mode") or "players")
        if nominate_mode not in ("players", "head"):
            nominate_mode = "players"

        current_uid = ctx.gint("day_current_uid")
        speeches_done = ctx.gbool("day_speeches_done")
        if nominate_mode != "head":
            if not current_uid:
                return {"ok": False, "error": "no_active_speech", "status": 409}

        elif not current_uid and not speeches_done:
            return {"ok": False, "error": "no_active_speech", "status": 409}

        if nominate_mode == "head":
            err = ctx.ensure_head(error="not_head", status=403)
            if err:
                return err

        elif current_uid != actor_uid:
            return {"ok": False, "error": "not_your_speech", "status": 403}

        pre_active = str(raw_gstate.get("day_prelude_active") or "0") == "1"
        pre_uid = ctx.gint("day_prelude_uid")
        if pre_active and pre_uid and current_uid == pre_uid:
            return {"ok": False, "error": "prelude_no_nomination", "status": 409}

        if str(raw_gstate.get("vote_blocked") or "0") == "1":
            return {"ok": False, "error": "vote_blocked", "status": 409}

        if nominate_mode != "head":
            err = await ctx.ensure_player()
            if err:
                return err

        err = await ctx.ensure_player(target_uid, error="target_not_alive", status=400)
        if err:
            return err

        if nominate_mode != "head":
            already_speaker = await r.sismember(f"room:{rid}:game_nom_speakers", str(current_uid))
            if already_speaker:
                return {"ok": False, "error": "already_nominated", "status": 409}

        existing_idx = await r.hget(f"room:{rid}:game_nominees", str(target_uid))
        if existing_idx is not None:
            return {"ok": False, "error": "target_already_on_ballot", "status": 409}

        try:
            cur_cnt = int(await r.hlen(f"room:{rid}:game_nominees") or 0)
        except Exception:
            cur_cnt = 0
        new_idx = cur_cnt + 1

        async with r.pipeline() as p:
            await p.hset(f"room:{rid}:game_nominees", str(target_uid), str(new_idx))
            if nominate_mode != "head":
                await p.sadd(f"room:{rid}:game_nom_speakers", str(current_uid))
            await p.execute()

        if nominate_mode != "head":
            await log_game_action(
                r,
                rid,
                {
                    "type": "nominate",
                    "actor_id": actor_uid,
                    "target_id": target_uid,
                    "day": ctx.gint("day_number"),
                },
            )

        ordered = await get_nominees_in_order(r, rid)
        payload = {
            "room_id": rid,
            "user_id": target_uid,
            "by": actor_uid,
            "index": new_idx,
            "order": ordered,
        }

        await sio.emit("game_nominee_added",
                       payload,
                       room=f"room:{rid}",
                       namespace="/room")

        return {"ok": True, "status": 200, **payload}

    except Exception:
        log.exception("sio.game_nominate.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_nominee_remove:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_nominee_remove(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid, allowed_phases="day")
        if err:
            return err

        actor_uid = ctx.uid
        rid = ctx.rid
        try:
            target_uid = int(data.get("user_id") or 0)
        except Exception:
            target_uid = 0
        if not target_uid:
            return {"ok": False, "error": "bad_request", "status": 400}

        r = ctx.r
        raw_gstate = ctx.gstate
        phase = ctx.phase
        if phase != "day":
            return {"ok": False, "error": "bad_phase", "status": 400}

        try:
            raw_game = await r.hgetall(f"room:{rid}:game")
        except Exception:
            raw_game = {}
        nominate_mode = str(raw_game.get("nominate_mode") or "players")
        if nominate_mode not in ("players", "head"):
            nominate_mode = "players"
        if nominate_mode != "head":
            return {"ok": False, "error": "not_head", "status": 403}

        err = ctx.ensure_head(error="not_head", status=403)
        if err:
            return err

        pre_active = str(raw_gstate.get("day_prelude_active") or "0") == "1"
        pre_uid = ctx.gint("day_prelude_uid")
        current_uid = ctx.gint("day_current_uid")
        if pre_active and pre_uid and current_uid == pre_uid:
            return {"ok": False, "error": "prelude_no_nomination", "status": 409}

        if str(raw_gstate.get("vote_blocked") or "0") == "1":
            return {"ok": False, "error": "vote_blocked", "status": 409}

        err = await ctx.ensure_player(target_uid, error="target_not_alive", status=400)
        if err:
            return err

        ordered = await get_nominees_in_order(r, rid)
        if not ordered:
            return {"ok": False, "error": "no_nominees", "status": 409}

        if target_uid not in ordered:
            return {"ok": False, "error": "not_nominated", "status": 409}

        ordered = [uid for uid in ordered if uid != target_uid]
        async with r.pipeline() as p:
            await p.delete(f"room:{rid}:game_nominees")
            if ordered:
                mapping = {str(uid): str(i + 1) for i, uid in enumerate(ordered)}
                await p.hset(f"room:{rid}:game_nominees", mapping=mapping)
            await p.execute()

        # Ведущийские номинации не логируем.

        payload = {
            "room_id": rid,
            "user_id": target_uid,
            "by": actor_uid,
            "order": ordered,
        }
        await sio.emit("game_nominee_removed",
                       payload,
                       room=f"room:{rid}",
                       namespace="/room")

        return {"ok": True, "status": 200, **payload}

    except Exception:
        log.exception("sio.game_nominee_remove.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_farewell_mark:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_farewell_mark(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid, allowed_phases=("day", "vote"))
        if err:
            return err

        speaker_uid = ctx.uid
        rid = ctx.rid
        r = ctx.r
        try:
            target_uid = int(data.get("user_id") or 0)
        except Exception:
            target_uid = 0
        if not target_uid:
            return {"ok": False, "error": "bad_request", "status": 400}

        verdict_raw = str(data.get("verdict") or data.get("color") or "")
        verdict = verdict_raw if verdict_raw in ("citizen", "mafia") else ""
        if not verdict:
            return {"ok": False, "error": "bad_request", "status": 400}

        phase = ctx.phase
        if phase == "day":
            cur_uid = ctx.gint("day_current_uid")
            pre_active = ctx.gbool("day_prelude_active")
            pre_uid = ctx.gint("day_prelude_uid")
            speech_in_progress = cur_uid == speaker_uid
            farewell_active = speech_in_progress and pre_active and pre_uid and pre_uid == cur_uid
        elif phase == "vote":
            cur_uid = ctx.gint("vote_speech_uid")
            kind = ctx.gstr("vote_speech_kind")
            vote_aborted = ctx.gbool("vote_aborted")
            speech_in_progress = cur_uid == speaker_uid and not vote_aborted
            farewell_active = speech_in_progress and kind == "farewell"
        else:
            return {"ok": False, "error": "bad_phase", "status": 400}

        if not speech_in_progress:
            return {"ok": False, "error": "no_active_speech", "status": 409}

        if not farewell_active:
            return {"ok": False, "error": "not_farewell", "status": 409}

        if target_uid == speaker_uid:
            return {"ok": False, "error": "self_target", "status": 400}

        err = await ctx.ensure_player(target_uid, error="target_not_alive", status=404)
        if err:
            return err

        is_alive = await r.sismember(f"room:{rid}:game_alive", str(target_uid))
        if not is_alive:
            return {"ok": False, "error": "target_not_alive", "status": 404}

        mode = "voted" if phase == "vote" else "killed"
        try:
            allowed = await compute_farewell_allowed(r, rid, speaker_uid, mode=mode)
        except Exception:
            allowed = True
        if not allowed:
            return {"ok": False, "error": "farewell_forbidden", "status": 409}

        limit = await ensure_farewell_limit(r, rid, speaker_uid, mode=mode)
        wills_for = await get_farewell_wills_for(r, rid, speaker_uid)
        used = len(wills_for)
        if limit <= 0 or used >= limit:
            return {"ok": False, "error": "limit_reached", "status": 409, "limit": limit, "used": used}

        tgt_key = f"{speaker_uid}:{target_uid}"
        if str(target_uid) in wills_for:
            return {"ok": False, "error": "already_marked", "status": 409, "limit": limit, "used": used}

        try:
            await r.hset(f"room:{rid}:game_farewell_wills", tgt_key, verdict)
        except Exception:
            log.exception("game_farewell_mark.save_failed", rid=rid, uid=speaker_uid, target=target_uid)
            return {"ok": False, "error": "internal", "status": 500}

        wills_for[str(target_uid)] = verdict
        payload = {
            "room_id": rid,
            "speaker_uid": speaker_uid,
            "target_uid": target_uid,
            "verdict": verdict,
            "wills": wills_for,
            "limit": limit,
            "remaining": max(limit - len(wills_for), 0),
            "allowed": allowed,
        }

        await sio.emit("game_farewell_update",
                       payload,
                       room=f"room:{rid}",
                       namespace="/room")

        return {"ok": True, "status": 200, **payload}

    except Exception:
        log.exception("sio.game_farewell_mark.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_best_move_start:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_best_move_start(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid, allowed_phases="night", require_head=True)
        if err:
            return err

        rid = ctx.rid
        r = ctx.r
        if ctx.phase != "night":
            return {"ok": False, "error": "bad_phase", "status": 400}

        stage = ctx.gstr("night_stage", "sleep")
        if stage != "checks_done":
            return {"ok": False, "error": "night_not_finished", "status": 409, "night_stage": stage}

        best_uid = ctx.gint("best_move_uid")
        if not best_uid:
            return {"ok": False, "error": "best_move_unavailable", "status": 409}

        if ctx.gbool("best_move_active"):
            return {"ok": False, "error": "already_active", "status": 409}

        try:
            await r.hset(f"room:{rid}:game_state", mapping={"best_move_active": "1"})
        except Exception:
            log.exception("game_best_move_start.save_failed", rid=rid, uid=ctx.uid)
            return {"ok": False, "error": "internal", "status": 500}

        raw_state = dict(ctx.gstate)
        raw_state["best_move_uid"] = str(best_uid)
        raw_state["best_move_active"] = "1"
        best_move = best_move_payload_from_state(GameActionContext.from_raw_state(uid=ctx.uid, rid=rid, r=r, raw_state=raw_state), include_empty=True)
        killed_uid, kill_ok = await compute_night_kill(r, rid, log_action_bool=False)
        payload = {
            "room_id": rid,
            "best_move": best_move,
            "night": {"kill_uid": killed_uid, "kill_ok": kill_ok},
        }
        await sio.emit("game_best_move_update",
                       payload,
                       room=f"room:{rid}",
                       namespace="/room")
        return {"ok": True, "status": 200, **payload}

    except Exception:
        log.exception("sio.game_best_move_start.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_best_move_mark:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_best_move_mark(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid, allowed_phases="night")
        if err:
            return err

        rid = ctx.rid
        r = ctx.r
        if ctx.phase != "night":
            return {"ok": False, "error": "bad_phase", "status": 400}

        stage = ctx.gstr("night_stage", "sleep")
        if stage != "checks_done":
            return {"ok": False, "error": "night_not_finished", "status": 409, "night_stage": stage}

        best_uid = ctx.gint("best_move_uid")
        if not best_uid:
            return {"ok": False, "error": "best_move_unavailable", "status": 409}

        if not ctx.gbool("best_move_active"):
            return {"ok": False, "error": "best_move_inactive", "status": 409}

        speaker_uid = ctx.uid
        if speaker_uid != best_uid:
            return {"ok": False, "error": "forbidden", "status": 403}

        try:
            target_uid = int(data.get("user_id") or 0)
        except Exception:
            target_uid = 0
        if not target_uid:
            return {"ok": False, "error": "bad_request", "status": 400}
        if target_uid == speaker_uid:
            return {"ok": False, "error": "self_target", "status": 400}

        existing_targets = ctx.gcsv_ints("best_move_targets")
        if target_uid in existing_targets:
            return {"ok": False, "error": "already_marked", "status": 409}

        if len(existing_targets) >= 3:
            return {"ok": False, "error": "limit_reached", "status": 409}

        is_alive = await r.sismember(f"room:{rid}:game_alive", str(target_uid))
        if not is_alive:
            return {"ok": False, "error": "target_not_alive", "status": 404}

        updated_targets = [*existing_targets, target_uid]
        targets_raw = ",".join(str(v) for v in updated_targets)
        try:
            await r.hset(f"room:{rid}:game_state", mapping={"best_move_targets": targets_raw})
        except Exception:
            log.exception("game_best_move_mark.save_failed", rid=rid, uid=speaker_uid, target=target_uid)
            return {"ok": False, "error": "internal", "status": 500}

        raw_state = dict(ctx.gstate)
        raw_state["best_move_uid"] = str(best_uid)
        raw_state["best_move_active"] = "1"
        raw_state["best_move_targets"] = targets_raw
        best_move = best_move_payload_from_state(GameActionContext.from_raw_state(uid=ctx.uid, rid=rid, r=r, raw_state=raw_state), include_empty=True)
        payload = {
            "room_id": rid,
            "speaker_uid": speaker_uid,
            "target_uid": target_uid,
            "best_move": best_move,
        }
        await sio.emit("game_best_move_update",
                       payload,
                       room=f"room:{rid}",
                       namespace="/room")
        return {"ok": True, "status": 200, **payload}

    except Exception:
        log.exception("sio.game_best_move_mark.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_vote_control:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_vote_control(sid, data):
    try:
        data = data or {}
        action = str(data.get("action") or "")
        ctx, err = await require_ctx(sid, allowed_phases="vote", require_head=True)
        if err:
            return err

        actor_uid = ctx.uid
        rid = ctx.rid
        r = ctx.r
        raw_gstate = ctx.gstate
        phase = ctx.phase
        if phase != "vote":
            return {"ok": False, "error": "bad_phase", "status": 400}

        head_uid = ctx.head_uid
        if not head_uid or actor_uid != head_uid:
            return {"ok": False, "error": "forbidden", "status": 403}

        vote_lift_state = str(raw_gstate.get("vote_lift_state") or "")
        if vote_lift_state:
            return {"ok": False, "error": "lift_in_progress", "status": 409}

        vote_done = str(raw_gstate.get("vote_done") or "0") == "1"
        if vote_done:
            return {"ok": False, "error": "vote_done", "status": 409}

        nominees = await get_nominees_in_order(r, rid)
        if not nominees:
            return {"ok": False, "error": "no_nominees", "status": 409}

        current_uid = ctx.gint("vote_current_uid")
        if current_uid and current_uid in nominees:
            cur_idx = nominees.index(current_uid)
        else:
            current_uid = nominees[0]
            cur_idx = 0

        total_nominees = len(nominees)
        vote_duration = ctx.gint("vote_duration", get_positive_setting_int("VOTE_SECONDS", 3))
        if vote_duration <= 0:
            vote_duration = 3

        alive_ids, voted_ids = await get_alive_and_voted_ids(r, rid)
        if alive_ids and alive_ids.issubset(voted_ids):
            async with r.pipeline() as p:
                await p.hset(f"room:{rid}:game_state", mapping={"vote_done": "1", "vote_started": "0"})
                await p.execute()

            await sio.emit("game_vote_state",
                           {"room_id": rid,
                            "vote": {"current_uid": current_uid,
                                     "deadline": 0,
                                     "nominees": nominees,
                                     "done": True}},
                           room=f"room:{rid}",
                           namespace="/room")
            return {"ok": True, "status": 200, "room_id": rid, "done": True}

        is_last = (cur_idx == total_nominees - 1)
        if action == "start":
            try:
                vote_started = int(raw_gstate.get("vote_started") or 0)
            except Exception:
                vote_started = 0

            if vote_started:
                now_ts = int(time())
                if vote_duration > 0 and now_ts < vote_started + vote_duration:
                    return {"ok": False, "error": "vote_in_progress", "status": 409}

                return {"ok": False, "error": "vote_already_ended", "status": 409}

            if is_last:
                to_auto_vote = [uid for uid in alive_ids if uid not in voted_ids]
                if to_auto_vote:
                    async with r.pipeline() as p:
                        for voter in to_auto_vote:
                            await p.hset(f"room:{rid}:game_votes", str(voter), str(current_uid))
                        await p.hset(f"room:{rid}:game_state", mapping={"vote_done": "1", "vote_started": "0"})
                        await p.execute()
                    for voter in to_auto_vote:
                        await sio.emit("game_voted",
                                       {"room_id": rid,
                                        "user_id": voter,
                                        "target_id": current_uid,
                                        "auto": True},
                                       room=f"room:{rid}",
                                       namespace="/room")
                else:
                    async with r.pipeline() as p:
                        await p.hset(f"room:{rid}:game_state", mapping={"vote_done": "1", "vote_started": "0"})
                        await p.execute()

                await sio.emit("game_vote_state",
                               {"room_id": rid,
                                "vote": {"current_uid": current_uid,
                                         "deadline": 0,
                                         "nominees": nominees,
                                         "done": True}},
                               room=f"room:{rid}",
                               namespace="/room")
                return {"ok": True, "status": 200, "room_id": rid, "done": True}

            now_ts = int(time())
            async with r.pipeline() as p:
                await p.hset(
                    f"room:{rid}:game_state",
                    mapping={
                        "vote_current_uid": str(current_uid),
                        "vote_started": str(now_ts),
                        "vote_duration": str(vote_duration),
                    },
                )
                await p.execute()

            await sio.emit("game_vote_state",
                           {"room_id": rid,
                            "vote": {"current_uid": current_uid,
                                     "deadline": vote_duration,
                                     "nominees": nominees,
                                     "done": False}},
                           room=f"room:{rid}",
                           namespace="/room")
            return {"ok": True, "status": 200, "room_id": rid, "current_uid": current_uid}

        elif action == "next":
            now_ts = int(time())
            try:
                vote_started = int(raw_gstate.get("vote_started") or 0)
            except Exception:
                vote_started = 0

            if vote_started and now_ts < vote_started + vote_duration:
                return {"ok": False, "error": "vote_in_progress", "status": 409}

            next_idx = cur_idx + 1
            if next_idx >= total_nominees:
                to_auto_vote = [uid for uid in alive_ids if uid not in voted_ids]
                if to_auto_vote:
                    async with r.pipeline() as p:
                        for voter in to_auto_vote:
                            await p.hset(f"room:{rid}:game_votes", str(voter), str(current_uid))
                        await p.hset(f"room:{rid}:game_state", mapping={"vote_done": "1", "vote_started": "0"})
                        await p.execute()
                    for voter in to_auto_vote:
                        await sio.emit("game_voted",
                                       {"room_id": rid,
                                        "user_id": voter,
                                        "target_id": current_uid,
                                        "auto": True},
                                       room=f"room:{rid}",
                                       namespace="/room")
                else:
                    async with r.pipeline() as p:
                        await p.hset(f"room:{rid}:game_state", mapping={"vote_done": "1", "vote_started": "0"})
                        await p.execute()

                await sio.emit("game_vote_state",
                               {"room_id": rid,
                                "vote": {"current_uid": current_uid,
                                         "deadline": 0,
                                         "nominees": nominees,
                                         "done": True}},
                               room=f"room:{rid}",
                               namespace="/room")
                return {"ok": True, "status": 200, "room_id": rid, "done": True}

            next_uid = nominees[next_idx]
            async with r.pipeline() as p:
                await p.hset(f"room:{rid}:game_state", mapping={"vote_current_uid": str(next_uid), "vote_started": "0"})
                await p.execute()

            await sio.emit("game_vote_state",
                           {"room_id": rid,
                            "vote": {"current_uid": next_uid,
                                     "deadline": 0,
                                     "nominees": nominees,
                                     "done": False}},
                           room=f"room:{rid}",
                           namespace="/room")
            return {"ok": True, "status": 200, "room_id": rid, "current_uid": next_uid}

        else:
            return {"ok": False, "error": "bad_action", "status": 400}

    except Exception:
        log.exception("sio.game_vote_control.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_vote:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_vote(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid, allowed_phases="vote")
        if err:
            return err

        uid = ctx.uid
        rid = ctx.rid
        r = ctx.r
        raw_gstate = ctx.gstate
        phase = ctx.phase
        if phase != "vote":
            return {"ok": False, "error": "bad_phase", "status": 400}

        vote_done = str(raw_gstate.get("vote_done") or "0") == "1"
        if vote_done:
            return {"ok": False, "error": "vote_done", "status": 409}

        err = await ctx.ensure_player()
        if err:
            return err

        vote_lift_state = str(raw_gstate.get("vote_lift_state") or "")
        is_lift_vote = vote_lift_state == "voting"
        nominee_uid = ctx.gint("vote_current_uid")
        if not nominee_uid and not is_lift_vote:
            return {"ok": False, "error": "no_active_vote", "status": 409}

        vote_started = ctx.gint("vote_started")
        vote_duration = ctx.gint("vote_duration", get_positive_setting_int("VOTE_SECONDS", 3))
        now_ts = int(time())
        if not vote_started or vote_duration <= 0 or now_ts > vote_started + vote_duration:
            return {"ok": False, "error": "vote_window_closed", "status": 409}

        existing = await r.hget(f"room:{rid}:game_votes", str(uid))
        if existing is not None:
            return {"ok": False, "error": "already_voted", "status": 409}

        store_value = "1" if is_lift_vote else str(nominee_uid)
        await r.hset(f"room:{rid}:game_votes", str(uid), store_value)

        await sio.emit("game_voted",
                       {"room_id": rid,
                        "user_id": uid,
                        "target_id": 0 if is_lift_vote else nominee_uid,
                        "auto": False,
                        "lift": is_lift_vote},
                       room=f"room:{rid}",
                       namespace="/room")

        alive_ids, voted_ids = await get_alive_and_voted_ids(r, rid)
        if alive_ids and alive_ids.issubset(voted_ids):
            async with r.pipeline() as p:
                await p.hset(f"room:{rid}:game_state", mapping={"vote_done": "1", "vote_started": "0"})
                await p.execute()

            nominees = await get_nominees_in_order(r, rid)
            await sio.emit("game_vote_state",
                           {"room_id": rid,
                            "vote": {"current_uid": 0 if is_lift_vote else nominee_uid,
                                     "deadline": 0,
                                     "nominees": nominees,
                                     "done": True,
                                     "lift_state": vote_lift_state if is_lift_vote else ""}},
                           room=f"room:{rid}",
                           namespace="/room")

        return {
            "ok": True,
            "status": 200,
            "room_id": rid,
            "user_id": uid,
            "target_id": 0 if is_lift_vote else nominee_uid
        }

    except Exception:
        log.exception("sio.game_vote.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_vote_finish:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_vote_finish(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid, allowed_phases="vote", require_head=True)
        if err:
            return err

        actor_uid = ctx.uid
        rid = ctx.rid
        r = ctx.r
        raw_gstate = ctx.gstate
        phase = ctx.phase
        if phase != "vote":
            return {"ok": False, "error": "bad_phase", "status": 400}

        head_uid = ctx.head_uid
        if not head_uid or actor_uid != head_uid:
            return {"ok": False, "error": "forbidden", "status": 403}

        vote_lift_state = str(raw_gstate.get("vote_lift_state") or "")
        vote_done = str(raw_gstate.get("vote_done") or "0") == "1"
        vote_results_ready = str(raw_gstate.get("vote_results_ready") or "0") == "1"
        if vote_results_ready and vote_lift_state != "voting":
            return {"ok": False, "error": "vote_results_ready", "status": 409}

        if not vote_done and vote_lift_state != "voting":
            return {"ok": False, "error": "vote_not_done", "status": 409}

        nominees = await get_nominees_in_order(r, rid)
        if not nominees:
            return {"ok": False, "error": "no_nominees", "status": 409}

        try:
            raw_votes = await r.hgetall(f"room:{rid}:game_votes")
        except Exception:
            raw_votes = {}

        day_number = ctx.gint("day_number")
        if vote_lift_state == "voting":
            voters: list[int] = []
            for voter_s in (raw_votes or {}).keys():
                try:
                    voter_i = int(voter_s)
                except Exception:
                    continue
                if voter_i > 0:
                    voters.append(voter_i)
            await log_game_action(
                r,
                rid,
                {
                    "type": "vote",
                    "lift": True,
                    "targets": nominees,
                    "by": voters,
                    "day": day_number,
                },
            )
        else:
            votes_by_target: dict[str, list[int]] = {str(uid): [] for uid in nominees}
            for voter_s, target_s in (raw_votes or {}).items():
                try:
                    voter_i = int(voter_s)
                    target_i = int(target_s or 0)
                except Exception:
                    continue
                if voter_i > 0 and target_i in nominees:
                    votes_by_target[str(target_i)].append(voter_i)
            if nominees:
                await log_game_action(
                    r,
                    rid,
                    {
                        "type": "vote",
                        "targets": nominees,
                        "votes": votes_by_target,
                        "day": day_number,
                    },
                )

        if vote_lift_state != "voting":
            votes_map: dict[int, int] = {}
            for voter_s, target_s in (raw_votes or {}).items():
                try:
                    voter_i = int(voter_s)
                    target_i = int(target_s or 0)
                except Exception:
                    continue
                if voter_i > 0:
                    votes_map[voter_i] = target_i
            if votes_map:
                await store_last_votes_snapshot(r, rid, votes_map)

        if vote_lift_state == "voting":
            alive_ids, voted_ids = await get_alive_and_voted_ids(r, rid)
            yes_cnt = len(voted_ids)
            alive_cnt = len(alive_ids)
            passed = alive_cnt > 0 and yes_cnt > (alive_cnt / 2)
            leaders = list(nominees) if passed else []
            leaders_str = ",".join(str(uid) for uid in leaders)

            payload = {
                "room_id": rid,
                "nominees": nominees,
                "leaders": leaders,
                "lift": True,
                "lift_state": "passed" if passed else "failed",
                "yes": yes_cnt,
                "alive": alive_cnt,
                "counts": {str(uid): 0 for uid in nominees},
            }

            async with r.pipeline() as p:
                mapping = {
                    "vote_leaders_order": leaders_str,
                    "vote_leader_idx": "0",
                    "vote_speech_uid": "0",
                    "vote_speech_started": "0",
                    "vote_speech_duration": "0",
                    "vote_speech_kind": "",
                    "vote_aborted": "0",
                    "vote_results_ready": "1",
                    "vote_speeches_done": "0" if passed else "1",
                    "vote_prev_leaders": "",
                    "vote_lift_state": "passed" if passed else "failed",
                    "vote_done": "1",
                    "vote_started": "0",
                    "vote_current_uid": "0",
                    "vote_blocked": "0",
                }
                await p.hset(f"room:{rid}:game_state", mapping=mapping)
                await p.delete(f"room:{rid}:game_votes")
                await p.delete(f"room:{rid}:game_nominees")
                if passed and leaders:
                    mp_nominees = {str(uid): str(i + 1) for i, uid in enumerate(leaders)}
                    await p.hset(f"room:{rid}:game_nominees", mapping=mp_nominees)
                await p.execute()

            await sio.emit("game_vote_result",
                           payload,
                           room=f"room:{rid}",
                           namespace="/room")
            return {"ok": True, "status": 200, **payload}

        counts: dict[int, int] = {uid: 0 for uid in nominees}
        for _voter_s, target_s in (raw_votes or {}).items():
            try:
                t = int(target_s or 0)
            except Exception:
                continue
            if t in counts:
                counts[t] = counts.get(t, 0) + 1

        max_votes = max(counts.values()) if counts else 0
        if max_votes <= 0:
            return {"ok": False, "error": "no_leaders", "status": 409}

        leaders: list[int] = [uid for uid in nominees if counts.get(uid, 0) == max_votes]
        prev_leaders = ctx.gcsv_ints("vote_prev_leaders")
        repeated = bool(prev_leaders) and len(prev_leaders) == len(leaders) and set(prev_leaders) == set(leaders) and len(leaders) > 1
        lift_state_new = "ready" if repeated else ""
        all_alive_leaders = False
        lift_forbidden = False
        if repeated and leaders:
            alive_ids, _ = await get_alive_and_voted_ids(r, rid)
            all_alive_leaders = bool(alive_ids) and set(leaders) == set(alive_ids)
            if not all_alive_leaders:
                leaders_cnt = len(leaders)
                if leaders_cnt in (2, 3, 5):
                    try:
                        raw_game = await r.hgetall(f"room:{rid}:game")
                    except Exception:
                        raw_game = {}
                    if day_number == 1 and not game_flag(raw_game, "lift_at_zero", True):
                        lift_forbidden = True
                    elif leaders_cnt == 3 and not game_flag(raw_game, "lift_3x", True):
                        try:
                            players_total = int(await r.scard(f"room:{rid}:game_players") or 0)
                        except Exception:
                            players_total = 0
                        if players_total == 9:
                            lift_forbidden = True

        no_elimination = all_alive_leaders or lift_forbidden
        if lift_forbidden:
            lift_state_new = ""
        payload = {
            "room_id": rid,
            "nominees": nominees,
            "leaders": leaders,
            "counts": {str(uid): int(counts.get(uid, 0)) for uid in nominees},
        }
        if lift_state_new:
            payload["lift_state"] = lift_state_new
        if no_elimination:
            payload["leaders"] = []
            payload["speeches_done"] = True
            lift_state_new = ""
            payload.pop("lift_state", None)

        await sio.emit("game_vote_result",
                       payload,
                       room=f"room:{rid}",
                       namespace="/room")

        leaders_str = ",".join(str(uid) for uid in leaders)
        async with r.pipeline() as p:
            await p.hset(
                f"room:{rid}:game_state",
                mapping={
                    "vote_leaders_order": "" if no_elimination else leaders_str,
                    "vote_leader_idx": "0",
                    "vote_speech_uid": "0",
                    "vote_speech_started": "0",
                    "vote_speech_duration": "0",
                    "vote_speech_kind": "",
                    "vote_aborted": "0",
                    "vote_results_ready": "1",
                    "vote_speeches_done": "1" if (lift_state_new or no_elimination) else "0",
                    "vote_prev_leaders": leaders_str if not no_elimination else "",
                    "vote_lift_state": lift_state_new,
                    "vote_blocked": "0",
                },
            )
            if no_elimination:
                await p.delete(f"room:{rid}:game_nominees")
            else:
                mp_nominees = {str(uid): str(i + 1) for i, uid in enumerate(leaders)}
                await p.delete(f"room:{rid}:game_nominees")
                if mp_nominees:
                    await p.hset(f"room:{rid}:game_nominees", mapping=mp_nominees)
            await p.execute()

        return {"ok": True, "status": 200, **payload}

    except Exception:
        log.exception("sio.game_vote_finish.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_vote_restart_current:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_vote_restart_current(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid, allowed_phases="vote", require_head=True)
        if err:
            return err

        rid = ctx.rid
        r = ctx.r
        raw_gstate = ctx.gstate
        current_uid = ctx.gint("vote_current_uid")
        target_uid = int(data.get("user_id") or 0)
        if target_uid <= 0:
            target_uid = current_uid
        if not target_uid:
            return {"ok": False, "error": "no_current_vote", "status": 409}

        vote_lift_state = str(raw_gstate.get("vote_lift_state") or "")
        if vote_lift_state:
            return {"ok": False, "error": "lift_in_progress", "status": 409}

        vote_done = str(raw_gstate.get("vote_done") or "0") == "1"
        if vote_done:
            return {"ok": False, "error": "vote_done", "status": 409}

        nominees = await get_nominees_in_order(r, rid)
        if not nominees:
            return {"ok": False, "error": "no_nominees", "status": 409}

        if target_uid not in nominees:
            return {"ok": False, "error": "no_current_vote", "status": 409}

        try:
            raw_votes = await r.hgetall(f"room:{rid}:game_votes")
        except Exception:
            raw_votes = {}
        remaining_votes: dict[str, str] = {}
        cleared_voters: list[int] = []
        for voter_raw, target_raw in (raw_votes or {}).items():
            try:
                voter = int(voter_raw)
                tgt = int(target_raw)
            except Exception:
                continue
            if tgt == target_uid:
                cleared_voters.append(voter)
            else:
                remaining_votes[str(voter)] = str(tgt)

        vote_duration = ctx.gint("vote_duration", get_positive_setting_int("VOTE_SECONDS", 3))
        if vote_duration <= 0:
            vote_duration = 3

        async with r.pipeline() as p:
            await p.hset(
                f"room:{rid}:game_state",
                mapping={
                    "vote_current_uid": str(target_uid),
                    "vote_started": "0",
                    "vote_duration": str(vote_duration),
                    "vote_done": "0",
                    "vote_aborted": "0",
                    "vote_results_ready": "0",
                    "vote_speech_uid": "0",
                    "vote_speech_started": "0",
                    "vote_speech_duration": "0",
                    "vote_speech_kind": "",
                },
            )
            await p.delete(f"room:{rid}:game_votes")
            if remaining_votes:
                await p.hset(f"room:{rid}:game_votes", mapping=remaining_votes)
            await p.execute()

        payload_vote = {
            "current_uid": target_uid,
            "deadline": 0,
            "nominees": nominees,
            "done": False,
            "restart": True,
            "cleared_voters": cleared_voters,
        }

        await sio.emit("game_vote_state",
                       {"room_id": rid,
                        "vote": payload_vote},
                       room=f"room:{rid}",
                       namespace="/room")

        return {"ok": True, "status": 200, "room_id": rid, **payload_vote}

    except Exception:
        log.exception("sio.game_vote_restart_current.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_vote_lift_prepare:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_vote_lift_prepare(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid, allowed_phases="vote", require_head=True)
        if err:
            return err

        actor_uid = ctx.uid
        rid = ctx.rid
        r = ctx.r
        raw_gstate = ctx.gstate
        if ctx.phase != "vote":
            return {"ok": False, "error": "bad_phase", "status": 400}

        head_uid = ctx.head_uid
        if not head_uid or actor_uid != head_uid:
            return {"ok": False, "error": "forbidden", "status": 403}

        vote_lift_state = str(raw_gstate.get("vote_lift_state") or "")
        vote_results_ready = str(raw_gstate.get("vote_results_ready") or "0") == "1"
        if vote_lift_state not in ("ready", "prepared"):
            return {"ok": False, "error": "lift_not_ready", "status": 409}

        if not vote_results_ready:
            return {"ok": False, "error": "vote_not_ready", "status": 409}

        async with r.pipeline() as p:
            await p.hset(f"room:{rid}:game_state", mapping={"vote_lift_state": "prepared"})
            await p.execute()

        nominees = await get_nominees_in_order(r, rid)
        vote_section = {
            "current_uid": 0,
            "deadline": 0,
            "nominees": nominees,
            "done": True,
            "aborted": ctx.gbool("vote_aborted"),
            "results_ready": vote_results_ready,
            "speeches_done": ctx.gbool("vote_speeches_done"),
            "lift_state": "prepared",
        }
        leaders = ctx.gcsv_ints("vote_leaders_order")
        if leaders:
            vote_section["leaders"] = leaders
            vote_section["leader_idx"] = ctx.gint("vote_leader_idx")

        await sio.emit("game_vote_state",
                       {"room_id": rid, "vote": vote_section},
                       room=f"room:{rid}",
                       namespace="/room")

        return {"ok": True, "status": 200, "room_id": rid, "vote_lift_state": "prepared"}

    except Exception:
        log.exception("sio.game_vote_lift_prepare.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_vote_lift_start:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_vote_lift_start(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid, allowed_phases="vote", require_head=True)
        if err:
            return err

        actor_uid = ctx.uid
        rid = ctx.rid
        r = ctx.r
        raw_gstate = ctx.gstate
        if ctx.phase != "vote":
            return {"ok": False, "error": "bad_phase", "status": 400}

        head_uid = ctx.head_uid
        if not head_uid or actor_uid != head_uid:
            return {"ok": False, "error": "forbidden", "status": 403}

        vote_lift_state = str(raw_gstate.get("vote_lift_state") or "")
        if vote_lift_state not in ("ready", "prepared"):
            return {"ok": False, "error": "lift_not_ready", "status": 409}

        nominees = await get_nominees_in_order(r, rid)
        if not nominees:
            return {"ok": False, "error": "no_nominees", "status": 409}

        now_ts = int(time())
        vote_duration = get_positive_setting_int("VOTE_SECONDS", 3)
        async with r.pipeline() as p:
            await p.hset(
                f"room:{rid}:game_state",
                mapping={
                    "vote_started": str(now_ts),
                    "vote_duration": str(vote_duration),
                    "vote_done": "0",
                    "vote_aborted": "0",
                    "vote_results_ready": "0",
                    "vote_speeches_done": "0",
                    "vote_current_uid": "0",
                    "vote_lift_state": "voting",
                    "vote_leader_idx": "0",
                    "vote_speech_uid": "0",
                    "vote_speech_started": "0",
                    "vote_speech_duration": "0",
                    "vote_speech_kind": "",
                    "vote_blocked": "0",
                },
            )
            await p.delete(f"room:{rid}:game_votes")
            await p.execute()

        payload = {
            "ok": True,
            "status": 200,
            "room_id": rid,
            "vote": {
                "current_uid": 0,
                "deadline": vote_duration,
                "nominees": nominees,
                "done": False,
                "aborted": False,
                "lift_state": "voting",
            },
        }
        await sio.emit("game_vote_state",
                       {"room_id": rid, "vote": payload["vote"]},
                       room=f"room:{rid}",
                       namespace="/room")

        return payload

    except Exception:
        log.exception("sio.game_vote_lift_start.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_speech_finish:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_speech_finish(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid, allowed_phases=("day", "vote"))
        if err:
            return err

        actor_uid = ctx.uid
        rid = ctx.rid
        r = ctx.r
        raw_gstate = ctx.gstate
        phase = ctx.phase
        if phase not in ("day", "vote"):
            return {"ok": False, "error": "bad_phase", "status": 400}

        if phase == "day":
            current_uid = ctx.gint("day_current_uid")
        else:
            current_uid = ctx.gint("vote_speech_uid")

        if not current_uid:
            return {"ok": False, "error": "no_speech", "status": 400}

        head_uid = ctx.head_uid
        if not head_uid:
            return {"ok": False, "error": "no_head", "status": 400}

        if actor_uid not in (head_uid, current_uid):
            return {"ok": False, "error": "forbidden", "status": 403}

        pre_active = str(raw_gstate.get("day_prelude_active") or "0") == "1"
        try:
            pre_uid = int(raw_gstate.get("day_prelude_uid") or 0)
        except Exception:
            pre_uid = 0
        if not (phase == "day" and pre_active and pre_uid and current_uid == pre_uid):
            is_alive = await r.sismember(f"room:{rid}:game_alive", str(current_uid))
            if not is_alive:
                return {"ok": False, "error": "not_alive", "status": 400}

        try:
            if phase == "day":
                if pre_active and pre_uid and current_uid == pre_uid:
                    payload = await finish_day_prelude_speech(r, rid, raw_gstate, current_uid)
                else:
                    payload = await finish_day_speech(r, rid, raw_gstate, current_uid)
            else:
                payload = await finish_vote_speech(r, rid, raw_gstate, current_uid)
        except Exception:
            log.exception("sio.game_speech_finish.finish_failed", rid=rid, uid=current_uid)
            return {"ok": False, "error": "internal", "status": 500}

        await sio.emit("game_day_speech",
                       payload,
                       room=f"room:{rid}",
                       namespace="/room")
        return {"ok": True, "status": 200, **payload}

    except Exception:
        log.exception("sio.game_speech_finish.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_vote_speech_next:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_vote_speech_next(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid, allowed_phases="vote", require_head=True)
        if err:
            return err

        actor_uid = ctx.uid
        rid = ctx.rid
        r = ctx.r
        raw_gstate = ctx.gstate
        phase = ctx.phase
        if phase != "vote":
            return {"ok": False, "error": "bad_phase", "status": 400}

        head_uid = ctx.head_uid
        if not head_uid or actor_uid != head_uid:
            return {"ok": False, "error": "forbidden", "status": 403}

        vote_done = str(raw_gstate.get("vote_done") or "0") == "1"
        if not vote_done:
            return {"ok": False, "error": "vote_not_done", "status": 409}

        cur_speaker = ctx.gint("vote_speech_uid")
        speech_started = ctx.gint("vote_speech_started")
        speech_duration = ctx.gint("vote_speech_duration")
        vote_lift_state = ctx.gstr("vote_lift_state")
        now_ts = int(time())
        if cur_speaker and speech_started and speech_duration > 0 and now_ts < speech_started + speech_duration:
            return {"ok": False, "error": "speech_in_progress", "status": 409}

        leaders = ctx.gcsv_ints("vote_leaders_order")
        if not leaders:
            return {"ok": False, "error": "no_leaders", "status": 409}

        leader_idx = ctx.gint("vote_leader_idx")
        total = len(leaders)
        if leader_idx >= total:
            return {"ok": False, "error": "no_more_leaders", "status": 409}

        target_uid = leaders[leader_idx]
        is_player = await r.sismember(f"room:{rid}:game_players", str(target_uid))
        is_alive = await r.sismember(f"room:{rid}:game_alive", str(target_uid))
        if not (is_player and is_alive):
            async with r.pipeline() as p:
                await p.hset(f"room:{rid}:game_state", "vote_leader_idx", str(leader_idx + 1))
                await p.execute()
            return await game_vote_speech_next(sid, data)

        full_sec = get_positive_setting_int("PLAYER_TALK_SECONDS", 60)
        short_sec = get_positive_setting_int("PLAYER_TALK_SHORT_SECONDS", 30)
        if short_sec <= 0:
            short_sec = full_sec
        shorten_farewell = False
        if total == 1 and ctx.gint("day_number") == 1:
            try:
                raw_game = await r.hgetall(f"room:{rid}:game")
            except Exception:
                raw_game = {}
            if not game_flag(raw_game, "break_at_zero", True):
                shorten_farewell = True

        if vote_lift_state == "passed":
            kind = "farewell"
            duration = full_sec
        elif total == 1:
            kind = "farewell"
            duration = short_sec if shorten_farewell else full_sec
        else:
            kind = "defence"
            duration = short_sec

        try:
            _, forced_off = await apply_blocks_and_emit(r, rid, actor_uid=head_uid, actor_role="head", target_uid=target_uid, changes_bool={"mic": False})
        except Exception:
            log.exception("game_vote_speech_next.unblock_mic_failed", rid=rid, head=head_uid, target=target_uid)
            return {"ok": False, "error": "internal", "status": 500}

        if "__error__" in forced_off:
            return {"ok": False, "error": "forbidden", "status": 403}

        try:
            await r.hset(f"room:{rid}:user:{target_uid}:state", mapping={"mic": "1"})
            await emit_state_changed_filtered(r, rid, target_uid, {"mic": "1"})
        except Exception:
            log.exception("game_vote_speech_next.mic_state_on_failed", rid=rid, uid=target_uid)

        now_ts = int(time())
        async with r.pipeline() as p:
            await p.hset(
                f"room:{rid}:game_state",
                mapping={
                    "vote_leader_idx": str(leader_idx + 1),
                    "vote_speech_uid": str(target_uid),
                    "vote_speech_started": str(now_ts),
                    "vote_speech_duration": str(duration),
                    "vote_speech_kind": kind,
                },
            )
            await p.execute()

        farewell_section: dict[str, Any] | None = None
        if kind == "farewell":
            try:
                limit = await ensure_farewell_limit(r, rid, target_uid, mode="voted")
                wills_for = await get_farewell_wills_for(r, rid, target_uid)
                allowed = await compute_farewell_allowed(r, rid, target_uid, mode="voted")
                farewell_section = {"limit": limit, "wills": wills_for, "allowed": allowed}
            except Exception:
                log.exception("game_vote_speech_next.farewell_build_failed", rid=rid, uid=target_uid)

        payload = {
            "room_id": rid,
            "speaker_uid": target_uid,
            "opening_uid": target_uid,
            "closing_uid": target_uid,
            "deadline": duration,
            "vote_speech_kind": kind,
        }
        if farewell_section:
            payload["farewell"] = farewell_section

        await sio.emit("game_day_speech",
                       payload,
                       room=f"room:{rid}",
                       namespace="/room")
        return {"ok": True, "status": 200, **payload}

    except Exception:
        log.exception("sio.game_vote_speech_next.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_vote_restart:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_vote_restart(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid, allowed_phases="vote", require_head=True)
        if err:
            return err

        actor_uid = ctx.uid
        rid = ctx.rid
        r = ctx.r
        raw_gstate = ctx.gstate
        phase = ctx.phase
        if phase != "vote":
            return {"ok": False, "error": "bad_phase", "status": 400}

        head_uid = ctx.head_uid
        if not head_uid or actor_uid != head_uid:
            return {"ok": False, "error": "forbidden", "status": 403}

        vote_done = str(raw_gstate.get("vote_done") or "0") == "1"
        if not vote_done:
            return {"ok": False, "error": "vote_not_done", "status": 409}

        leaders = ctx.gcsv_ints("vote_leaders_order")
        leader_idx = ctx.gint("vote_leader_idx")
        if len(leaders) > 1 and leader_idx < len(leaders):
            return {"ok": False, "error": "speeches_not_done", "status": 409}

        ordered = await get_nominees_in_order(r, rid)
        if not ordered:
            return {"ok": False, "error": "no_nominees", "status": 409}

        first_uid = ordered[0]
        vote_duration = get_positive_setting_int("VOTE_SECONDS", 3)
        async with r.pipeline() as p:
            await p.hset(
                f"room:{rid}:game_state",
                mapping={
                    "vote_current_uid": str(first_uid or 0),
                    "vote_started": "0",
                    "vote_duration": str(vote_duration),
                    "vote_done": "0",
                    "vote_aborted": "0",
                    "vote_speech_uid": "0",
                    "vote_speech_started": "0",
                    "vote_speech_duration": "0",
                    "vote_speech_kind": "",
                    "vote_results_ready": "0",
                    "vote_speeches_done": "0",
                    "vote_lift_state": "",
                    "vote_blocked": "0",
                    "vote_blocked_next": "0",
                },
            )
            await p.delete(f"room:{rid}:game_votes")
            await p.execute()

        payload = {
            "ok": True,
            "status": 200,
            "room_id": rid,
            "vote": {
                "nominees": ordered,
                "current_uid": first_uid,
                "deadline": 0,
                "done": False,
                "aborted": False,
            },
        }

        await sio.emit("game_vote_state",
                       {"room_id": rid,
                        "vote": payload["vote"]},
                       room=f"room:{rid}",
                       namespace="/room")
        return payload

    except Exception:
        log.exception("sio.game_vote_restart.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:night_shoot_start:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_night_shoot_start(sid, data):
    try:
        ctx, err = await require_ctx(sid, allowed_phases="night", require_head=True)
        if err:
            return err

        uid = ctx.uid
        rid = ctx.rid
        r = ctx.r
        g = ctx.gstate
        if ctx.phase != "night":
            return {"ok": False, "error": "bad_phase", "status": 400}

        head_uid = ctx.head_uid
        if not head_uid or uid != head_uid:
            return {"ok": False, "error": "forbidden", "status": 403}

        stage = str(g.get("night_stage") or "sleep")
        if stage != "sleep":
            return {"ok": False, "error": "bad_stage", "status": 409}

        now_ts = int(time())
        try:
            dur = get_cached_settings().night_action_seconds
        except Exception:
            dur = 10
        if dur <= 0:
            dur = 10

        async with r.pipeline() as p:
            await p.hset(
                f"room:{rid}:game_state",
                mapping={
                    "night_stage": "shoot",
                    "night_shoot_started": str(now_ts),
                    "night_shoot_duration": str(dur),
                },
            )
            await p.delete(f"room:{rid}:night_shots")
            await p.execute()

        g2 = dict(g)
        g2["night_stage"] = "shoot"
        g2["night_shoot_started"] = str(now_ts)
        g2["night_shoot_duration"] = str(dur)
        await emit_game_night_state(rid, g2)
        asyncio.create_task(night_stage_timeout_job(rid, "shoot", now_ts, dur, "shoot_done"))
        return {"ok": True, "status": 200, "room_id": rid}

    except Exception:
        log.exception("sio.game_night_shoot_start.error", sid=sid)
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:night_shoot:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_night_shoot(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid, allowed_phases="night")
        if err:
            return err

        uid = ctx.uid
        rid = ctx.rid
        target_uid = int(data.get("user_id") or 0)
        if not target_uid:
            return {"ok": False, "error": "bad_request", "status": 400}

        r = ctx.r
        g = ctx.gstate
        if ctx.phase != "night":
            return {"ok": False, "error": "bad_phase", "status": 400}

        if str(g.get("night_stage") or "sleep") != "shoot":
            return {"ok": False, "error": "bad_stage", "status": 409}

        started = ctx.gint("night_shoot_started")
        dur = ctx.gint("night_shoot_duration")
        now_ts = int(time())
        if not started or dur <= 0 or now_ts > started + dur:
            return {"ok": False, "error": "window_closed", "status": 409}

        err = await ctx.ensure_player()
        if err:
            return err

        role = str((await r.hget(f"room:{rid}:game_roles", str(uid))) or "")
        if role not in ("mafia", "don"):
            return {"ok": False, "error": "forbidden", "status": 403}

        err = await ctx.ensure_player(target_uid, alive_required=False, error="bad_target", status=400)
        if err:
            return err

        existing = await r.hget(f"room:{rid}:night_shots", str(uid))
        if existing is not None:
            return {"ok": False, "error": "already_chosen", "status": 409}

        await r.hset(f"room:{rid}:night_shots", str(uid), str(target_uid))
        try:
            seat = int((await r.hget(f"room:{rid}:game_seats", str(target_uid))) or 0)
        except Exception:
            seat = 0
        try:
            head_uid = int(g.get("head") or 0)
        except Exception:
            head_uid = 0
        if head_uid:
            await emit_night_head_picks(r, rid, "shoot", head_uid)

        return {
            "ok": True,
            "status": 200,
            "room_id": rid,
            "user_id": uid,
            "target_id": target_uid,
            "kind": "shoot",
            "seat": seat
        }

    except Exception:
        log.exception("sio.game_night_shoot.error", sid=sid)
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:night_checks_start:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_night_checks_start(sid, data):
    try:
        ctx, err = await require_ctx(sid, allowed_phases="night", require_head=True)
        if err:
            return err

        uid = ctx.uid
        rid = ctx.rid
        r = ctx.r
        g = ctx.gstate
        if ctx.phase != "night":
            return {"ok": False, "error": "bad_phase", "status": 400}

        head_uid = ctx.head_uid
        if not head_uid or uid != head_uid:
            return {"ok": False, "error": "forbidden", "status": 403}

        stage = str(g.get("night_stage") or "sleep")
        if stage != "shoot_done":
            return {"ok": False, "error": "bad_stage", "status": 409}

        now_ts = int(time())
        try:
            dur = get_cached_settings().night_action_seconds
        except Exception:
            dur = 10
        if dur <= 0:
            dur = 10

        async with r.pipeline() as p:
            await p.hset(
                f"room:{rid}:game_state",
                mapping={
                    "night_stage": "checks",
                    "night_check_started": str(now_ts),
                    "night_check_duration": str(dur),
                },
            )
            await p.delete(f"room:{rid}:night_checks")
            await p.execute()

        g2 = dict(g)
        g2["night_stage"] = "checks"
        g2["night_check_started"] = str(now_ts)
        g2["night_check_duration"] = str(dur)
        await emit_game_night_state(rid, g2)
        asyncio.create_task(night_stage_timeout_job(rid, "checks", now_ts, dur, "checks_done"))
        return {"ok": True, "status": 200, "room_id": rid}

    except Exception:
        log.exception("sio.game_night_checks_start.error", sid=sid)
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:night_check:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_night_check(sid, data):
    try:
        data = data or {}
        ctx, err = await require_ctx(sid, allowed_phases="night")
        if err:
            return err

        uid = ctx.uid
        rid = ctx.rid
        target_uid = int(data.get("user_id") or 0)
        if not target_uid:
            return {"ok": False, "error": "bad_request", "status": 400}

        r = ctx.r
        g = ctx.gstate
        if ctx.phase != "night":
            return {"ok": False, "error": "bad_phase", "status": 400}

        if str(g.get("night_stage") or "sleep") != "checks":
            return {"ok": False, "error": "bad_stage", "status": 409}

        started = ctx.gint("night_check_started")
        dur = ctx.gint("night_check_duration")
        now_ts = int(time())
        if not started or dur <= 0 or now_ts > started + dur:
            return {"ok": False, "error": "window_closed", "status": 409}

        err = await ctx.ensure_player()
        if err:
            return err

        my_role = str((await r.hget(f"room:{rid}:game_roles", str(uid))) or "")
        if my_role not in ("don", "sheriff"):
            return {"ok": False, "error": "forbidden", "status": 403}

        if target_uid == uid:
            return {"ok": False, "error": "bad_target", "status": 400}

        err = await ctx.ensure_player(target_uid, alive_required=False, error="bad_target", status=400)
        if err:
            return err

        checked_key = f"room:{rid}:game_checked:{my_role}"
        if await r.sismember(checked_key, str(target_uid)):
            return {"ok": False, "error": "already_checked", "status": 409}

        if my_role == "don":
            tr = str((await r.hget(f"room:{rid}:game_roles", str(target_uid))) or "")
            if tr in ("mafia", "don"):
                return {"ok": False, "error": "bad_target", "status": 400}

        existing = await r.hget(f"room:{rid}:night_checks", str(uid))
        if existing is not None:
            return {"ok": False, "error": "already_chosen", "status": 409}

        await r.hset(f"room:{rid}:night_checks", str(uid), str(target_uid))
        await r.sadd(checked_key, str(target_uid))
        try:
            seat = int((await r.hget(f"room:{rid}:game_seats", str(target_uid))) or 0)
        except Exception:
            seat = 0
        try:
            head_uid = int(g.get("head") or 0)
        except Exception:
            head_uid = 0
        if head_uid:
            await emit_night_head_picks(r, rid, "checks", head_uid)

        target_role = str((await r.hget(f"room:{rid}:game_roles", str(target_uid))) or "")
        if my_role == "sheriff":
            shown = "mafia" if target_role in ("mafia", "don") else "citizen"
        else:
            shown = "sheriff" if target_role == "sheriff" else "citizen"

        await log_game_action(
            r,
            rid,
            {
                "type": "night_check",
                "actor_id": uid,
                "target_id": target_uid,
                "target_role": target_role,
                "checker_role": my_role,
                "day": ctx.gint("day_number"),
            },
        )

        await sio.emit("game_night_reveal",
                       {"room_id": rid,
                        "target_id": target_uid,
                        "shown_role": shown},
                       room=f"user:{uid}",
                       namespace="/room")

        return {
            "ok": True,
            "status": 200,
            "room_id": rid,
            "user_id": uid,
            "target_id": target_uid,
            "kind": "checks",
            "seat": seat
        }

    except Exception:
        log.exception("sio.game_night_check.error", sid=sid)
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_end:{uid or 'nouid'}:{rid or 0}", limit=10, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_end(sid, data):
    try:
        data = data or {}
        confirm = bool(data.get("confirm"))
        sess = await sio.get_session(sid, namespace="/room")
        ctx, err = await require_ctx(sid, require_head=True)
        if err:
            return err

        return await perform_game_end(ctx, sess, confirm=confirm, reason="manual")

    except Exception:
        log.exception("sio.game_end.error", sid=sid)
        return {"ok": False, "error": "internal", "status": 500}


@sio.event(namespace="/room")
async def disconnect(sid):
    try:
        sess = await sio.get_session(sid, namespace="/room")
        if not sess or "uid" not in sess:
            return

        uid = int(sess["uid"])
        actor_user_name = str(sess.get("username") or f"user{uid}")
        rid = int(sess.get("rid") or 0)
        if not rid:
            return

        r = get_redis()
        is_spectator = bool(sess.get("spectator"))
        if not is_spectator:
            try:
                is_spectator = await r.sismember(f"room:{rid}:spectators", str(uid))
            except Exception:
                is_spectator = False
        if is_spectator:
            await record_spectator_leave(r, rid, uid, int(time()))
        try:
            sess_epoch = int(sess.get("epoch") or 0)
        except Exception:
            sess_epoch = 0

        cur_epoch = int(await r.get(f"room:{rid}:user:{uid}:epoch") or 0)
        if cur_epoch > sess_epoch:
            return

        await stop_screen_for_user(r, rid, uid, actor_uid=uid, actor_username=actor_user_name)

        try:
            phase = str(await r.hget(f"room:{rid}:game_state", "phase") or "idle")
        except Exception:
            phase = "idle"

        async def leave_and_collect():
            was_member = await r.sismember(f"room:{rid}:members", str(uid))
            if was_member:
                occ, gc_seq, pos_updates = await leave_room_atomic(r, rid, uid)
            else:
                occ = int(await r.scard(f"room:{rid}:members") or 0)
                gc_seq = 0
                pos_updates = []
            return was_member, occ, gc_seq, pos_updates

        async def cleanup_ready_epoch():
            try:
                await r.srem(f"room:{rid}:ready", str(uid))
            except Exception as err:
                log.warning("sio.disconnect.ready_delete_failed", rid=rid, uid=uid, err=type(err).__name__)
            try:
                await r.delete(f"room:{rid}:user:{uid}:epoch")
            except Exception as err:
                log.warning("sio.disconnect.epoch_delete_failed", rid=rid, uid=uid, err=type(err).__name__)

        async def emit_leave_events(was_member, pos_updates):
            if was_member:
                await sio.emit("member_left",
                               {"user_id": uid},
                               room=f"room:{rid}",
                               namespace="/room")
            if pos_updates:
                await sio.emit("positions",
                               {"updates": [{"user_id": u, "position": p} for u, p in pos_updates]},
                               room=f"room:{rid}",
                               namespace="/room")

        async def gc_if_empty(occ, gc_seq, *, schedule: bool):
            if occ != 0 or phase != "idle":
                return

            async def _gc():
                try:
                    removed = await gc_empty_room(rid, expected_seq=gc_seq)
                    if removed:
                        await sio.emit("rooms_remove",
                                       {"id": rid},
                                       namespace="/rooms")
                except Exception:
                    log.exception("gc.failed", rid=rid)

            if schedule:
                asyncio.create_task(_gc())
            else:
                await _gc()

        if phase == "idle":
            try:
                has_bg_state = await r.exists(f"room:{rid}:user:{uid}:bg_state")
            except Exception:
                has_bg_state = 0

            if has_bg_state:
                async def _bg_cleanup():
                    await asyncio.sleep(605)

                    try:
                        cur_epoch = int(await r.get(f"room:{rid}:user:{uid}:epoch") or 0)
                        if cur_epoch != sess_epoch:
                            return

                        was_member, occ, gc_seq, pos_updates = await leave_and_collect()
                        await cleanup_ready_epoch()
                        await emit_leave_events(was_member, pos_updates)
                        await emit_rooms_occupancy_safe(r, rid, occ)
                        await gc_if_empty(occ, gc_seq, schedule=False)

                    except Exception:
                        log.exception("sio.bg_disconnect.cleanup_failed", rid=rid, uid=uid)

                asyncio.create_task(_bg_cleanup())

                return

        was_member, occ, gc_seq, pos_updates = await leave_and_collect()
        await cleanup_ready_epoch()

        await sio.leave_room(sid,
                             f"room:{rid}",
                             namespace="/room")
        await emit_leave_events(was_member, pos_updates)

        await emit_rooms_occupancy_safe(r, rid, occ)

        base_role = str(sess.get("base_role") or "user")
        await sio.save_session(sid,
                               {"uid": uid,
                                "rid": None,
                                "role": base_role,
                                "base_role": base_role,
                                "username": sess.get("username"),
                                "avatar_name": sess.get("avatar_name")},
                               namespace="/room")

        await gc_if_empty(occ, gc_seq, schedule=True)

    except Exception:
        log.exception("sio.disconnect.error", sid=sid)
