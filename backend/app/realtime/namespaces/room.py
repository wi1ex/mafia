from __future__ import annotations
import asyncio
import random
from time import time
import structlog
from ..sio import sio
from ...core.clients import get_redis
from ...core.decorators import rate_limited_sio
from ...core.logging import log_action
from ...core.db import SessionLocal
from ...core.settings import settings
from ...schemas.realtime import StateAck, ModerateAck, JoinAck, ScreenAck, GameStartAck, GameRolePickAck
from ...services.livekit_tokens import make_livekit_token
from ..utils import (
    KEYS_STATE,
    KEYS_BLOCK,
    apply_state,
    gc_empty_room,
    get_room_snapshot,
    merge_ready_into_snapshot,
    set_ready,
    get_positions_map,
    build_game_from_raw,
    persist_join_user_info,
    get_blocks_snapshot,
    get_roles_snapshot,
    get_profiles_snapshot,
    join_room_atomic,
    leave_room_atomic,
    update_blocks,
    validate_auth,
    claim_screen,
    release_screen,
    account_screen_time,
    get_rooms_brief,
    init_roles_deck,
    advance_roles_turn,
    assign_role_for_user,
    emit_rooms_occupancy_safe,
    get_game_runtime_and_roles_view,
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


@rate_limited_sio(lambda *, uid=None, **__: f"rl:sio:join:{uid or 'nouid'}", limit=5, window_s=1, session_ns="/room")
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

        if int(params.get("creator") or 0) != uid and (params.get("privacy") or "open") == "private":
            allowed = await r.sismember(f"room:{rid}:allow", str(uid))
            if not allowed:
                pending = await r.sismember(f"room:{rid}:pending", str(uid))
                return {"ok": False, "error": "private_room", "status": 403, "pending": bool(pending)}

        raw_gstate = await r.hgetall(f"room:{rid}:game_state")
        phase = str(raw_gstate.get("phase") or "idle")
        if phase != "idle":
            head_raw = raw_gstate.get("head")
            head_id = int(head_raw) if head_raw else 0
            game_players_set = await r.smembers(f"room:{rid}:game_players")
            allowed_ids = {head_id} | {int(x) for x in (game_players_set or [])}
            if uid not in allowed_ids:
                return {"ok": False, "error": "game_in_progress", "status": 409}

        occ, pos, already, pos_updates = await join_room_atomic(r, rid, uid, base_role)
        if occ == -3:
            log.warning("sio.join.room_closed", rid=rid, uid=uid)
            return {"ok": False, "error": "room_closed", "status": 410}

        if occ == -1:
            log.warning("sio.join.room_full", rid=rid, uid=uid)
            return {"ok": False, "error": "room_is_full", "status": 409}

        await persist_join_user_info(r, rid, uid, sess.get("username"), sess.get("avatar_name"))
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
        profiles = await get_profiles_snapshot(r, rid)

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
                                "epoch": epoch},
                               namespace="/room")

        incoming = (data.get("state") or {}) if isinstance(data, dict) else {}
        user_state = {k: str(v) for k, v in (snapshot.get(str(uid)) or {}).items()}
        to_fill = {k: incoming[k] for k in KEYS_STATE if k in incoming and k not in user_state}
        if to_fill:
            applied = await apply_state(r, rid, uid, to_fill)
            if applied:
                user_state = {**user_state, **applied}
                snapshot[str(uid)] = user_state
                await sio.emit("state_changed",
                               {"user_id": uid, **applied},
                               room=f"room:{rid}",
                               skip_sid=sid,
                               namespace="/room")

        if not already:
            phase = str((await r.hget(f"room:{rid}:game_state", "phase")) or "idle")
            if phase != "idle":
                alive_occ = int(await r.scard(f"room:{rid}:game_alive") or 0)
                occ_to_send = alive_occ
            else:
                occ_to_send = occ

            await sio.emit("rooms_occupancy",
                           {"id": rid, "occupancy": occ_to_send},
                           namespace="/rooms")
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

        positions = await get_positions_map(r, rid)
        owner_raw = await r.get(f"room:{rid}:screen_owner")
        owner = int(owner_raw) if owner_raw else 0
        token = make_livekit_token(identity=str(uid), name=ev_username, room=str(rid))
        game = build_game_from_raw(await r.hgetall(f"room:{rid}:game"))
        game_runtime, game_roles_view, my_game_role = await get_game_runtime_and_roles_view(r, rid, uid)

        return {
            "ok": True,
            "room_id": rid,
            "token": token,
            "privacy": str(params.get("privacy") or "open"),
            "snapshot": snapshot,
            "self_pref": user_state,
            "positions": positions,
            "blocked": blocked,
            "roles": roles,
            "profiles": profiles,
            "screen_owner": owner,
            "game": game,
            "game_runtime": game_runtime,
            "game_roles": game_roles_view,
            "my_game_role": my_game_role,
        }

    except Exception:
        log.exception("sio.join.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:state:{uid or 'nouid'}:{rid or 0}", limit=30, window_s=1, session_ns="/room")
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
        payload = data or {}
        applied = await apply_state(r, rid, uid, payload)
        changed = dict(applied)
        if "ready" in payload:
            newv = await set_ready(r, rid, uid, payload.get("ready"))
            if newv is not None:
                changed["ready"] = newv
        if changed:
            await sio.emit("state_changed",
                           {"user_id": uid, **changed},
                           room=f"room:{rid}",
                           namespace="/room")
        return {"ok": True}

    except Exception:
        log.exception("sio.state.error", sid=sid)
        return {"ok": False}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:screen:{uid or 'nouid'}:{rid or 0}", limit=5, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def screen(sid, data) -> ScreenAck:
    try:
        sess = await sio.get_session(sid, namespace="/room")
        actor_uid = int(sess["uid"])
        rid = int(sess.get("rid") or 0)
        if not rid:
            return {"ok": False, "error": "no_room", "status": 400}

        r = get_redis()
        want_on = bool((data or {}).get("on"))
        target = int((data or {}).get("target") or actor_uid)

        if not await r.sismember(f"room:{rid}:members", str(target)):
            return {"ok": False, "error": "not_in_room", "status": 403}

        if target != actor_uid:
            role_in_room = await r.hget(f"room:{rid}:user:{actor_uid}:info", "role")
            actor_role = str(role_in_room or sess.get("role") or "user")
            trg_role = str(await r.hget(f"room:{rid}:user:{target}:info", "role") or "user")
            if actor_role not in ("admin", "host"):
                return {"ok": False, "error": "forbidden", "status": 403}

            if actor_role == "host" and trg_role == "admin":
                return {"ok": False, "error": "forbidden", "status": 403}

            if actor_role == trg_role:
                return {"ok": False, "error": "forbidden", "status": 403}

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
            return {"ok": True, "on": True}

        cur = await r.get(f"room:{rid}:screen_owner")
        if cur and int(cur) == target:
            if not bool((data or {}).get("canceled")):
                await account_screen_time(r, rid, target)
            else:
                await r.delete(f"room:{rid}:screen_started_at")

        changed = await release_screen(r, rid, target)
        if changed:
            await sio.emit("screen_owner",
                           {"user_id": None},
                           room=f"room:{rid}",
                           namespace="/room")
            await sio.emit("rooms_stream",
                           {"id": rid, "owner": None},
                           namespace="/rooms")

        return {"ok": True, "on": False}

    except Exception:
        log.exception("sio.screen.error", sid=sid)
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:moderate:{uid or 'nouid'}:{rid or 0}", limit=30, window_s=1, session_ns="/room")
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

        applied, forced_off = await update_blocks(r, rid, actor_uid, actor_role, target, norm)
        if "__error__" in forced_off:
            err = forced_off["__error__"]
            return {"ok": False, "error": err, "status": 403}

        if forced_off:
            await sio.emit("state_changed",
                           {"user_id": target, **forced_off},
                           room=f"room:{rid}",
                           namespace="/room")
        if applied:
            row = await r.hgetall(f"room:{rid}:user:{target}:block")
            full = {k: ("1" if (row or {}).get(k) == "1" else "0") for k in KEYS_BLOCK}
            await sio.emit("moderation",
                           {"user_id": target,
                            "blocks": full,
                            "by": {"user_id": actor_uid, "role": actor_role}},
                           room=f"room:{rid}",
                           namespace="/room")
            if applied.get("screen") == "1":
                cur = await r.get(f"room:{rid}:screen_owner")
                if cur and int(cur) == target:
                    await account_screen_time(r, rid, target)
                    await r.delete(f"room:{rid}:screen_owner")
                    await sio.emit("screen_owner",
                                   {"user_id": None},
                                   room=f"room:{rid}",
                                   namespace="/room")
                    await sio.emit("rooms_stream",
                                   {"id": rid, "owner": None},
                                   namespace="/rooms")

        if applied or forced_off:
            async with SessionLocal() as s:
                await log_action(
                    s,
                    user_id=actor_uid,
                    username=actor_user_name,
                    action="room_blocks",
                    details=f"Блокировка в комнате room_id={rid} target_user={target} actor_role={actor_role} applied={applied} forced_off={forced_off}",
                )

        return {"ok": True, "applied": applied, "forced_off": forced_off}

    except Exception:
        log.exception("sio.moderate.error", sid=sid)
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:kick:{uid or 'nouid'}:{rid or 0}", limit=5, window_s=1, session_ns="/room")
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
        if actor_role not in ("admin", "host"):
            return {"ok": False, "error": "forbidden", "status": 403}

        if actor_role == "host" and trg_role == "admin":
            return {"ok": False, "error": "forbidden", "status": 403}

        if actor_role == trg_role:
            return {"ok": False, "error": "forbidden", "status": 403}

        await r.srem(f"room:{rid}:allow", str(target))
        await r.srem(f"room:{rid}:pending", str(target))
        await sio.emit("force_leave",
                       {"room_id": rid,
                        "by": {"user_id": actor_uid, "role": actor_role}},
                       room=f"user:{target}",
                       namespace="/room")

        cur = await r.get(f"room:{rid}:screen_owner")
        if cur and int(cur) == target:
            await account_screen_time(r, rid, target)
            await r.delete(f"room:{rid}:screen_owner")
            await sio.emit("screen_owner",
                           {"user_id": None},
                           room=f"room:{rid}",
                           namespace="/room")
            await sio.emit("rooms_stream",
                           {"id": rid, "owner": None},
                           namespace="/rooms")

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

        async with SessionLocal() as s:
            await log_action(
                s,
                user_id=actor_uid,
                username=actor_user_name,
                action="room_kick",
                details=f"Кик из комнаты room_id={rid} target_user={target} actor_role={actor_role}",
            )

        return {"ok": True}

    except Exception:
        log.exception("sio.kick.error", sid=sid)
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_leave:{uid or 'nouid'}:{rid or 0}", limit=5, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_leave(sid, data):
    try:
        sess = await sio.get_session(sid, namespace="/room")
        uid = int(sess["uid"])
        rid = int(sess.get("rid") or 0)
        if not rid:
            return {"ok": False, "error": "no_room", "status": 400}

        r = get_redis()
        raw_gstate = await r.hgetall(f"room:{rid}:game_state")
        phase = str(raw_gstate.get("phase") or "idle")
        if phase == "idle":
            return {"ok": False, "error": "no_game", "status": 400}

        try:
            head_uid = int(raw_gstate.get("head") or 0)
        except Exception:
            head_uid = 0

        is_player = await r.sismember(f"room:{rid}:game_players", str(uid))
        if not is_player:
            return {"ok": False, "error": "not_player", "status": 400}

        was_alive = await r.sismember(f"room:{rid}:game_alive", str(uid))
        if not was_alive:
            return {"ok": False, "error": "already_dead", "status": 400}

        await r.srem(f"room:{rid}:game_alive", str(uid))

        try:
            alive_cnt = int(await r.scard(f"room:{rid}:game_alive") or 0)
        except Exception:
            alive_cnt = 0

        await sio.emit("rooms_occupancy",
                       {"id": rid, "occupancy": alive_cnt},
                       namespace="/rooms")

        try:
            await sio.emit("game_player_left",
                           {"room_id": rid, "user_id": uid},
                           room=f"room:{rid}",
                           namespace="/room")
        except Exception:
            log.exception("sio.game_leave.notify_failed", rid=rid, uid=uid)

        if head_uid and head_uid != uid:
            try:
                applied, forced_off = await update_blocks(r, rid, head_uid, "head", uid, {"mic": True, "cam": True})
            except Exception:
                log.exception("sio.game_leave.autoblock_failed", rid=rid, head=head_uid, target=uid)
            else:
                if forced_off:
                    await sio.emit("state_changed",
                                   {"user_id": uid, **forced_off},
                                   room=f"room:{rid}",
                                   namespace="/room")
                if applied:
                    row = await r.hgetall(f"room:{rid}:user:{uid}:block")
                    full = {k: ("1" if (row or {}).get(k) == "1" else "0") for k in KEYS_BLOCK}
                    await sio.emit("moderation",
                                   {"user_id": uid,
                                    "blocks": full,
                                    "by": {"user_id": head_uid, "role": "head"}},
                                   room=f"room:{rid}",
                                   namespace="/room")

        try:
            async with SessionLocal() as s:
                await log_action(
                    s,
                    user_id=uid,
                    username=str(sess.get("username") or f"user{uid}"),
                    action="game_leave",
                    details=f"Выход из игры room_id={rid}",
                )
        except Exception:
            log.exception("sio.game_leave.log_failed", rid=rid, uid=uid)

        return {"ok": True, "status": 200, "room_id": rid}

    except Exception:
        log.exception("sio.game_leave.error", sid=sid)
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_start:{uid or 'nouid'}:{rid or 0}", limit=5, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_start(sid, data) -> GameStartAck:
    try:
        data = data or {}
        confirm = bool(data.get("confirm"))
        sess = await sio.get_session(sid, namespace="/room")
        uid = int(sess["uid"])
        rid = int(sess.get("rid") or 0)
        if not rid:
            return {"ok": False, "error": "no_room", "status": 400}

        r = get_redis()
        params = await r.hgetall(f"room:{rid}:params")
        if not params:
            return {"ok": False, "error": "room_not_found", "status": 404}

        raw_gstate = await r.hgetall(f"room:{rid}:game_state")
        cur_phase = str(raw_gstate.get("phase") or "idle")
        if cur_phase != "idle":
            return {"ok": False, "error": "already_started", "status": 409}

        if not await r.sismember(f"room:{rid}:members", str(uid)):
            return {"ok": False, "error": "not_in_room", "status": 403}

        min_ready = settings.GAME_MIN_READY_PLAYERS
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
                "blocking_users": blocking_users,
            }

        conflict_users: set[int] = set()
        participants: set[int] = {head_uid} | {int(x) for x in (ready_ids or [])}
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
            return {
                "ok": False,
                "status": 409,
                "error": "already_in_other_game",
                "room_id": rid,
                "conflict_users": list(conflict_users),
            }

        if not confirm:
            return {
                "ok": True,
                "status": 200,
                "room_id": rid,
                "can_start": True,
                "min_ready": min_ready,
            }

        player_ids = [str(x) for x in ready_ids if str(x) != str(head_uid)]
        random.shuffle(player_ids)
        seats: dict[str, int] = {}
        slot = 1
        for pid in player_ids:
            seats[pid] = slot
            slot += 1
        seats[str(head_uid)] = 11
        now_ts = int(time())
        async with r.pipeline() as p:
            await p.hset(f"room:{rid}:game_state",
                         mapping={
                             "phase": "roles_pick",
                             "started_at": str(now_ts),
                             "started_by": str(uid),
                             "head": str(head_uid),
                         })
            if seats:
                await p.hset(f"room:{rid}:game_seats", mapping={k: str(v) for k, v in seats.items()})

            if player_ids:
                await p.delete(f"room:{rid}:game_players", f"room:{rid}:game_alive")
                await p.sadd(f"room:{rid}:game_players", *player_ids)
                await p.sadd(f"room:{rid}:game_alive", *player_ids)
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
                    applied, forced_off = await update_blocks(r, rid, head_uid, "head", target_uid, {"mic": True, "visibility": True})
                except Exception:
                    log.exception("sio.game_start.autoblock_failed", rid=rid, head=head_uid, target=pid)
                    continue

                if forced_off:
                    await sio.emit("state_changed",
                                   {"user_id": target_uid, **forced_off},
                                   room=f"room:{rid}",
                                   namespace="/room")
                if applied:
                    row = await r.hgetall(f"room:{rid}:user:{target_uid}:block")
                    full = {k: ("1" if (row or {}).get(k) == "1" else "0") for k in KEYS_BLOCK}
                    await sio.emit("moderation",
                                   {"user_id": target_uid,
                                    "blocks": full,
                                    "by": {"user_id": head_uid, "role": "head"}},
                                   room=f"room:{rid}",
                                   namespace="/room")

        payload: GameStartAck = {
            "ok": True,
            "status": 200,
            "room_id": rid,
            "phase": "roles_pick",
            "min_ready": min_ready,
            "seats": {k: int(v) for k, v in seats.items()},
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
                    details=f"Запуск игры room_id={rid} ready={ready_cnt}",
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
        sess = await sio.get_session(sid, namespace="/room")
        uid = int(sess["uid"])
        rid = int(sess.get("rid") or 0)
        if not rid:
            return {"ok": False, "error": "no_room", "status": 400}

        r = get_redis()
        raw_state = await r.hgetall(f"room:{rid}:game_state")
        phase = str(raw_state.get("phase") or "idle")
        if phase != "roles_pick":
            return {"ok": False, "error": "bad_phase", "status": 400}

        try:
            turn_uid = int(raw_state.get("roles_turn_uid") or 0)
        except Exception:
            turn_uid = 0
        if uid != turn_uid:
            return {"ok": False, "error": "not_your_turn", "status": 403}

        is_player = await r.sismember(f"room:{rid}:game_players", str(uid))
        try:
            head_uid = int(raw_state.get("head") or 0)
        except Exception:
            head_uid = 0
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


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_phase_next:{uid or 'nouid'}:{rid or 0}", limit=5, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_phase_next(sid, data):
    try:
        data = data or {}
        want_from = str(data.get("from") or "")
        want_to = str(data.get("to") or "")

        sess = await sio.get_session(sid, namespace="/room")
        uid = int(sess["uid"])
        rid = int(sess.get("rid") or 0)
        if not rid:
            return {"ok": False, "error": "no_room", "status": 400}

        r = get_redis()
        raw_gstate = await r.hgetall(f"room:{rid}:game_state")
        cur_phase = str(raw_gstate.get("phase") or "idle")
        if cur_phase == "idle":
            return {"ok": False, "error": "no_game", "status": 400}

        try:
            head_uid = int(raw_gstate.get("head") or 0)
        except Exception:
            head_uid = 0

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
                    applied, forced_off = await update_blocks(r, rid, head_uid, "head", target_uid, {"visibility": False})
                except Exception:
                    log.exception("sio.game_phase_next.mafia_unblock_failed", rid=rid, head=head_uid, target=target_uid)
                    continue

                if "__error__" in forced_off:
                    continue

                if applied:
                    row = await r.hgetall(f"room:{rid}:user:{target_uid}:block")
                    full = {k: ("1" if (row or {}).get(k) == "1" else "0") for k in KEYS_BLOCK}
                    await sio.emit("moderation",
                                   {"user_id": target_uid,
                                    "blocks": full,
                                    "by": {"user_id": head_uid, "role": "head"}},
                                   room=f"room:{rid}",
                                   namespace="/room")

            if mafia_targets:
                async with r.pipeline() as p:
                    for target_uid in mafia_targets:
                        await p.hset(f"room:{rid}:user:{target_uid}:state", mapping={"visibility": "1"})
                    await p.execute()

                for target_uid in mafia_targets:
                    await sio.emit("state_changed",
                                   {"user_id": target_uid,
                                    "visibility": "1"},
                                   room=f"room:{rid}",
                                   namespace="/room")

            now_ts = int(time())
            duration = int(getattr(settings, "MAFIA_TALK_SECONDS", 60))
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
                    await sio.emit("state_changed",
                                   {"user_id": target_uid,
                                    "visibility": "0"},
                                   room=f"room:{rid}",
                                   namespace="/room")

            for target_uid in mafia_targets:
                try:
                    applied, forced_off = await update_blocks(r, rid, head_uid, "head", target_uid, {"visibility": True})
                except Exception:
                    log.exception("sio.game_phase_next.mafia_reblock_failed", rid=rid, head=head_uid, target=target_uid)
                    continue

                if "__error__" in forced_off:
                    continue

                if forced_off:
                    await sio.emit("state_changed",
                                   {"user_id": target_uid, **forced_off},
                                   room=f"room:{rid}",
                                   namespace="/room")
                if applied:
                    row = await r.hgetall(f"room:{rid}:user:{target_uid}:block")
                    full = {k: ("1" if (row or {}).get(k) == "1" else "0") for k in KEYS_BLOCK}
                    await sio.emit("moderation",
                                   {"user_id": target_uid,
                                    "blocks": full,
                                    "by": {"user_id": head_uid, "role": "head"}},
                                   room=f"room:{rid}",
                                   namespace="/room")

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

        return {"ok": False, "error": "bad_transition", "status": 400, "from": cur_phase, "to": want_to}
    except Exception:
        log.exception("sio.game_phase_next.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@rate_limited_sio(lambda *, uid=None, rid=None, **__: f"rl:sio:game_end:{uid or 'nouid'}:{rid or 0}", limit=5, window_s=1, session_ns="/room")
@sio.event(namespace="/room")
async def game_end(sid, data):
    try:
        data = data or {}
        confirm = bool(data.get("confirm"))
        sess = await sio.get_session(sid, namespace="/room")
        uid = int(sess["uid"])
        rid = int(sess.get("rid") or 0)
        if not rid:
            return {"ok": False, "error": "no_room", "status": 400}

        r = get_redis()
        raw_gstate = await r.hgetall(f"room:{rid}:game_state")
        phase = str(raw_gstate.get("phase") or "idle")
        if phase == "idle":
            return {"ok": False, "error": "no_game", "status": 400}

        try:
            head_uid = int(raw_gstate.get("head") or 0)
        except Exception:
            head_uid = 0

        if not head_uid or uid != head_uid:
            return {"ok": False, "error": "forbidden", "status": 403}

        if not confirm:
            return {"ok": True, "status": 200, "room_id": rid, "can_end": True}

        try:
            players_set = await r.smembers(f"room:{rid}:game_players")
        except Exception:
            log.exception("sio.game_end.load_players_failed", rid=rid)
            players_set = set()

        for v in (players_set or []):
            try:
                target_uid = int(v)
            except Exception:
                continue
            if target_uid == head_uid:
                continue
            try:
                applied, forced_off = await update_blocks(r, rid, head_uid, "head", target_uid,
                                                          {"mic": False, "cam": False, "speakers": False, "visibility": False})
            except Exception:
                log.exception("sio.game_end.auto_unblock_failed", rid=rid, head=head_uid, target=target_uid)
                continue

            if "__error__" in forced_off:
                continue

            if applied:
                row = await r.hgetall(f"room:{rid}:user:{target_uid}:block")
                full = {k: ("1" if (row or {}).get(k) == "1" else "0") for k in KEYS_BLOCK}
                await sio.emit("moderation",
                               {"user_id": target_uid,
                                "blocks": full,
                                "by": {"user_id": head_uid, "role": "head"}},
                               room=f"room:{rid}",
                               namespace="/room")

        async with r.pipeline() as p:
            await p.delete(
                f"room:{rid}:game_state",
                f"room:{rid}:game_seats",
                f"room:{rid}:game_players",
                f"room:{rid}:game_alive",
            )
            await p.execute()

        try:
            occ = int(await r.scard(f"room:{rid}:members") or 0)
        except Exception:
            occ = 0

        await sio.emit("rooms_occupancy",
                       {"id": rid, "occupancy": occ},
                       namespace="/rooms")

        try:
            briefs = await get_rooms_brief(r, [rid])
            if briefs:
                await sio.emit("rooms_upsert",
                               briefs[0],
                               namespace="/rooms")
        except Exception:
            log.exception("sio.game_end.rooms_upsert_failed", rid=rid)

        await sio.emit("game_ended",
                       {"room_id": rid},
                       room=f"room:{rid}",
                       namespace="/room")

        try:
            async with SessionLocal() as s:
                await log_action(
                    s,
                    user_id=uid,
                    username=str(sess.get("username") or f"user{uid}"),
                    action="game_end",
                    details=f"Завершение игры room_id={rid} phase={phase}",
                )
        except Exception:
            log.exception("sio.game_end.log_failed", rid=rid, uid=uid)

        return {"ok": True, "status": 200, "room_id": rid}

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
        rid = int(sess.get("rid") or 0)
        if not rid:
            return

        r = get_redis()
        try:
            sess_epoch = int(sess.get("epoch") or 0)
        except Exception:
            sess_epoch = 0

        cur_epoch = int(await r.get(f"room:{rid}:user:{uid}:epoch") or 0)
        if cur_epoch > sess_epoch:
            return

        owner = await r.get(f"room:{rid}:screen_owner")
        if owner and int(owner) == uid:
            await account_screen_time(r, rid, uid)
            await r.delete(f"room:{rid}:screen_owner")
            await sio.emit("screen_owner",
                           {"user_id": None},
                           room=f"room:{rid}",
                           namespace="/room")
            await sio.emit("rooms_stream",
                           {"id": rid, "owner": None},
                           namespace="/rooms")

        was_member = await r.sismember(f"room:{rid}:members", str(uid))
        if was_member:
            occ, gc_seq, pos_updates = await leave_room_atomic(r, rid, uid)
        else:
            occ = int(await r.scard(f"room:{rid}:members") or 0)
            gc_seq = 0
            pos_updates = []

        try:
            await r.srem(f"room:{rid}:ready", str(uid))
        except Exception as e:
            log.warning("sio.disconnect.ready_delete_failed", rid=rid, uid=uid, err=type(e).__name__)
        try:
            await r.delete(f"room:{rid}:user:{uid}:epoch")
        except Exception as e:
            log.warning("sio.disconnect.epoch_delete_failed", rid=rid, uid=uid, err=type(e).__name__)

        await sio.leave_room(sid,
                             f"room:{rid}",
                             namespace="/room")
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

        try:
            phase = str(await r.hget(f"room:{rid}:game_state", "phase") or "idle")
        except Exception:
            phase = "idle"

        if occ == 0 and phase == "idle":
            async def _gc():
                try:
                    removed = await gc_empty_room(rid, expected_seq=gc_seq)
                    if removed:
                        await sio.emit("rooms_remove",
                                       {"id": rid},
                                       namespace="/rooms")
                except Exception:
                    log.exception("gc.failed", rid=rid)

            asyncio.create_task(_gc())

    except Exception:
        log.exception("sio.disconnect.error", sid=sid)
