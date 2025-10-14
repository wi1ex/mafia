from __future__ import annotations
import asyncio
import structlog
from ..sio import sio
from ..utils import validate_auth, claim_screen, release_screen
from ...core.clients import get_redis
from ...core.decorators import rate_limited_sio
from ...schemas import StateAck, ModerateAck, JoinAck, ScreenAck
from ...services.livekit_tokens import make_livekit_token
from ..utils import (
    KEYS_STATE,
    KEYS_BLOCK,
    apply_state,
    gc_empty_room,
    get_room_snapshot,
    get_blocks_snapshot,
    get_roles_snapshot,
    get_profiles_snapshot,
    join_room_atomic,
    leave_room_atomic,
    update_blocks,
    load_user_profile,
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
                           {"uid": uid, "rid": None, "role": role, "base_role": role, "username": username, "avatar_name": avatar_name},
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
        occ, pos, already, pos_updates = await join_room_atomic(r, rid, uid, base_role)
        if occ == -2:
            log.warning("sio.join.room_not_found", rid=rid, uid=uid)
            return {"ok": False, "error": "room_not_found", "status": 404}

        if occ == -1:
            log.info("sio.join.room_full", rid=rid, uid=uid)
            return {"ok": False, "error": "room_is_full", "status": 409}

        owner_id = await r.get(f"room:{rid}:screen_owner")
        owner = int(owner_id) if owner_id else 0
        db_username, db_avatar = await load_user_profile(uid)
        username, avatar_name = (sess.get("username") or None) or (db_username or None), db_avatar
        if username is not None or avatar_name is not None:
            await r.hset(f"room:{rid}:user:{uid}:info", mapping={
                **({"username": username} if username is not None else {}),
                **({"avatar_name": avatar_name} if avatar_name is not None else {}),
            })

        applied: dict[str, str] = {}
        snapshot = await get_room_snapshot(r, rid)
        blocked = await get_blocks_snapshot(r, rid)
        roles_map = await get_roles_snapshot(r, rid)
        profiles = await get_profiles_snapshot(r, rid)
        incoming = (data.get("state") or {}) if isinstance(data, dict) else {}
        user_state: dict[str, str] = {k: str(v) for k, v in (snapshot.get(str(uid)) or {}).items()}
        to_fill = {k: incoming[k] for k in KEYS_STATE if k in incoming and k not in user_state}
        if to_fill:
            applied = await apply_state(r, rid, uid, to_fill)
            if applied:
                user_state = {**user_state, **applied}
                snapshot[str(uid)] = user_state

        await sio.enter_room(sid,
                             f"room:{rid}",
                             namespace="/room")
        eff_blocks = blocked.get(str(uid)) or {}
        eff_role = roles_map.get(str(uid), base_role)
        await sio.save_session(sid,
                               {"uid": uid, "rid": rid, "role": eff_role, "base_role": base_role, "username": username, "avatar_name": avatar_name},
                               namespace="/room")
        if not already:
            await sio.emit("rooms_occupancy",
                           {"id": rid, "occupancy": occ},
                           namespace="/rooms")
            await sio.emit("member_joined",
                           {"user_id": uid, "state": user_state, "role": eff_role, "blocks": eff_blocks, "username": username, "avatar_name": avatar_name},
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
        if applied:
            await sio.emit("state_changed",
                           {"user_id": uid, **applied},
                           room=f"room:{rid}",
                           skip_sid=sid,
                           namespace="/room")

        redis_positions = await r.zrange(f"room:{rid}:positions", 0, -1, withscores=True)
        positions = {str(int(m)): int(s) for m, s in redis_positions}

        lk_token = make_livekit_token(identity=str(uid), name=(username or f"user-{uid}"), room=str(rid))
        return {
            "ok": True,
            "room_id": rid,
            "token": lk_token,
            "snapshot": snapshot,
            "self_pref": user_state,
            "positions": positions,
            "blocked": blocked,
            "roles": roles_map,
            "profiles": profiles,
            "screen_owner": owner,
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
            log.info("sio.state.no_rid", uid=uid)
            return {"ok": False}

        r = get_redis()
        applied = await apply_state(r, rid, uid, data or {})
        if applied:
            await sio.emit("state_changed",
                           {"user_id": uid, **applied},
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
            if actor_role not in ("admin", "host"):
                return {"ok": False, "error": "forbidden", "status": 403}

            trg_role = str(await r.hget(f"room:{rid}:user:{target}:info", "role") or "user")
            if actor_role == "host" and trg_role == "admin":
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
            return {"ok": True, "on": True}

        changed = await release_screen(r, rid, target)
        if changed:
            await sio.emit("screen_owner",
                           {"user_id": None},
                           room=f"room:{rid}",
                           namespace="/room")
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
            log.info("sio.moderate.no_changes", actor_uid=actor_uid, rid=rid)
            return {"ok": False, "error": "no_changes", "status": 400}

        r = get_redis()
        role_in_room = await r.hget(f"room:{rid}:user:{actor_uid}:info", "role")
        actor_role = str(role_in_room or sess.get("role") or "user")
        applied, forced_off = await update_blocks(r, rid, actor_uid, actor_role, target, norm)
        if "__error__" in forced_off:
            err = forced_off["__error__"]
            return {"ok": False, "error": err, "status": 404 if err == "user_not_in_room" else 403}

        if forced_off:
            await sio.emit("state_changed",
                           {"user_id": target, **forced_off},
                           room=f"room:{rid}",
                           namespace="/room")
        if applied:
            row = await r.hgetall(f"room:{rid}:user:{target}:block")
            full = {k: ("1" if (row or {}).get(k) == "1" else "0") for k in KEYS_BLOCK}
            await sio.emit("moderation",
                           {"user_id": target, "blocks": full, "by": {"user_id": actor_uid, "role": actor_role}},
                           room=f"room:{rid}",
                           namespace="/room")
            if applied.get("screen") == "1":
                cur = await r.get(f"room:{rid}:screen_owner")
                if cur and int(cur) == target:
                    await r.delete(f"room:{rid}:screen_owner")
                    await sio.emit("screen_owner",
                                   {"user_id": None},
                                   room=f"room:{rid}",
                                   namespace="/room")
        return {"ok": True, "applied": applied, "forced_off": forced_off}

    except Exception:
        log.exception("sio.moderate.error", sid=sid)
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
        owner = await r.get(f"room:{rid}:screen_owner")
        if owner and int(owner) == uid:
            await r.delete(f"room:{rid}:screen_owner")
            await sio.emit("screen_owner",
                           {"user_id": None},
                           room=f"room:{rid}",
                           namespace="/room")

        occ, gc_seq, pos_updates = await leave_room_atomic(r, rid, uid)

        await sio.leave_room(sid, f"room:{rid}", namespace="/room")
        await sio.emit("member_left",
                       {"user_id": uid},
                       room=f"room:{rid}",
                       namespace="/room")
        if pos_updates:
            await sio.emit("positions",
                           {"updates": [{"user_id": u, "position": p} for u, p in pos_updates]},
                           room=f"room:{rid}",
                           namespace="/room")
        await sio.emit("rooms_occupancy",
                       {"id": rid, "occupancy": occ},
                       namespace="/rooms")

        base_role = str(sess.get("base_role") or "user")
        await sio.save_session(sid,
                               {"uid": uid, "rid": None, "role": base_role, "base_role": base_role, "username": sess.get("username"), "avatar_name": sess.get("avatar_name")},
                               namespace="/room")
        if occ == 0:
            async def _gc():
                try:
                    removed = await gc_empty_room(rid, expected_seq=gc_seq)
                    if removed:
                        await sio.emit("rooms_remove",
                                       {"id": rid},
                                       namespace="/rooms")
                except Exception:
                    log.exception("gc failed rid=%s", rid)
            asyncio.create_task(_gc())

    except Exception:
        log.exception("sio.disconnect.error", sid=sid)
