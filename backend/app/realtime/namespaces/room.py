from __future__ import annotations
import asyncio
import structlog
from ..sio import sio
from ..utils import validate_auth
from ...core.clients import get_redis
from ...schemas import JoinAck
from ...services.livekit_tokens import make_livekit_token
from ..utils import (
    apply_state,
    gc_empty_room,
    get_room_snapshot,
    join_room_atomic,
    leave_room_atomic,
)

log = structlog.get_logger()


@sio.event(namespace="/room")
async def connect(sid, environ, auth):
    vr = await validate_auth(auth)
    if not vr:
        return False

    uid, role = vr
    await sio.save_session(sid, {"uid": uid, "rid": None, "role": role}, namespace="/room")
    await sio.enter_room(sid, f"user:{uid}", namespace="/room")


@sio.event(namespace="/room")
async def join(sid, data) -> JoinAck:
    try:
        sess = await sio.get_session(sid, namespace="/room")
        uid = int(sess["uid"])
        role = str(sess.get("role") or "user")
        rid = int((data or {}).get("room_id") or 0)
        if not rid:
            log.warning("sio.join.bad_room_id", sid=sid)
            return {"ok": False, "error": "bad_room_id", "status": 400}

        r = get_redis()
        occ, pos, already = await join_room_atomic(r, rid, uid, role)
        if occ == -2:
            log.warning("sio.join.room_not_found", rid=rid, uid=uid)
            return {"ok": False, "error": "room_not_found", "status": 404}

        if occ == -1:
            log.info("sio.join.room_full", rid=rid, uid=uid)
            return {"ok": False, "error": "room_is_full", "status": 409}

        applied: dict[str, str] = {}
        snapshot = await get_room_snapshot(r, rid)
        incoming = (data.get("state") or {}) if isinstance(data, dict) else {}
        user_state: dict[str, str] = {k: str(v) for k, v in (snapshot.get(str(uid)) or {}).items()}
        to_fill = {k: incoming[k] for k in ("mic", "cam", "speakers", "visibility") if k in incoming and k not in user_state}
        if to_fill:
            applied = await apply_state(r, rid, uid, to_fill)
            if applied:
                user_state = {**user_state, **applied}
                snapshot[str(uid)] = user_state

        await sio.enter_room(sid, f"room:{rid}", namespace="/room")
        await sio.save_session(sid, {"uid": uid, "rid": rid, "role": role}, namespace="/room")

        if not already:
            await sio.emit("rooms_occupancy", {"id": rid, "occupancy": occ}, namespace="/rooms")
            await sio.emit("member_joined", {"user_id": uid, "state": user_state, "role": role}, room=f"room:{rid}", skip_sid=sid, namespace="/room")

        await sio.emit("positions", {"updates": [{"user_id": uid, "position": pos}]}, room=f"room:{rid}", skip_sid=sid, namespace="/room")

        if applied:
            await sio.emit("state_changed", {"user_id": uid, **applied}, room=f"room:{rid}", skip_sid=sid, namespace="/room")

        redis_positions = await r.zrange(f"room:{rid}:positions", 0, -1, withscores=True)
        positions = {m: int(s) for m, s in redis_positions if m.isdigit()}
        lk_token = make_livekit_token(identity=str(uid), name=f"user-{uid}", room=str(rid))

        log.info("sio.join.ok", rid=rid, uid=uid, pos=pos, occ=occ, already=already)
        return {"ok": True, "room_id": rid, "token": lk_token, "snapshot": snapshot, "self_pref": user_state, "positions": positions}
    except Exception:
        log.exception("sio.join.error", sid=sid, data=bool(data))
        return {"ok": False, "error": "internal", "status": 500}


@sio.event(namespace="/room")
async def state(sid, data):
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
            await sio.emit("state_changed", {"user_id": uid, **applied}, room=f"room:{rid}", namespace="/room")
        else:
            log.info("sio.state.no_changes", uid=uid, rid=rid)
        return {"ok": True}

    except Exception:
        log.exception("sio.state.error", sid=sid)
        return {"ok": False}


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
        occ, gc_seq, pos_updates = await leave_room_atomic(r, rid, uid)

        await sio.leave_room(sid, f"room:{rid}", namespace="/room")
        await sio.emit("member_left", {"user_id": uid}, room=f"room:{rid}", namespace="/room")
        if pos_updates:
            await sio.emit("positions", {"updates": [{"user_id": u, "position": p} for u, p in pos_updates]}, room=f"room:{rid}", namespace="/room")
        await sio.emit("rooms_occupancy", {"id": rid, "occupancy": occ}, namespace="/rooms")
        await sio.save_session(sid, {"uid": uid, "rid": None, "role": sess.get("role")}, namespace="/room")

        if occ == 0:
            async def _gc():
                try:
                    removed = await gc_empty_room(rid, expected_seq=gc_seq)
                    if removed:
                        await sio.emit("rooms_remove", {"id": rid}, namespace="/rooms")
                except Exception:
                    log.exception("gc failed rid=%s", rid)
            asyncio.create_task(_gc())

        log.info("sio.disconnect.ok", uid=uid, rid=rid, occ=occ, updates=len(pos_updates))
    except Exception:
        log.exception("sio.disconnect.error", sid=sid)
