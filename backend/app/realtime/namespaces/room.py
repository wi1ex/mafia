from __future__ import annotations
import asyncio
import structlog
from jwt import ExpiredSignatureError
from ..sio import sio
from ...core.clients import get_redis
from ...core.security import decode_token
from ...schemas import JoinAck
from ...services.livekit_tokens import make_livekit_token
from ...utils import apply_state, gc_empty_room, get_room_snapshot, join_room_atomic, leave_room_atomic

log = structlog.get_logger()


@sio.event(namespace="/room")
async def connect(sid, environ, auth):
    try:
        token = auth.get("token") if isinstance(auth, dict) else None
        if not token:
            log.warning("sio.connect.no_token")
            raise ConnectionRefusedError("no_token")
        uid = int(decode_token(token)["sub"])
        await sio.save_session(sid, {"uid": uid, "rid": None}, namespace="/room")
    except ExpiredSignatureError:
        log.warning("sio.connect.expired_token")
        raise ConnectionRefusedError("expired_token")
    except Exception:
        log.warning("sio.connect.bad_token")
        raise ConnectionRefusedError("bad_token")


@sio.event(namespace="/room")
async def join(sid, data) -> JoinAck:
    try:
        sess = await sio.get_session(sid, namespace="/room")
        uid = int(sess["uid"])
        rid = int((data or {}).get("room_id") or 0)
        if not rid:
            return {"ok": False, "error": "bad_room_id", "status": 400}

        r = get_redis()
        occ = await join_room_atomic(r, rid, uid)
        if occ == -2:
            return {"ok": False, "error": "room_not_found", "status": 404}
        if occ == -1:
            return {"ok": False, "error": "room_is_full", "status": 409}
        await r.delete(f"room:{rid}:empty_since")

        applied: dict[str, str] = {}
        snapshot = await get_room_snapshot(r, rid)
        incoming = (data.get("state") or {}) if isinstance(data, dict) else {}
        user_state: dict[str, str] = {k: str(v) for k, v in (snapshot.get(str(uid)) or {}).items()}
        if not user_state and incoming:
            applied = await apply_state(r, rid, uid, incoming)
            if applied:
                user_state = {**user_state, **applied}
                snapshot[str(uid)] = user_state
        elif user_state and incoming:
            to_fill = {}
            for k in ("mic", "cam", "speakers", "visibility"):
                if k in incoming and k not in user_state:
                    to_fill[k] = incoming[k]
            if to_fill:
                applied = await apply_state(r, rid, uid, to_fill)
                if applied:
                    user_state = {**user_state, **applied}
                    snapshot[str(uid)] = user_state

        await sio.enter_room(sid, f"room:{rid}", namespace="/room")
        await sio.save_session(sid, {"uid": uid, "rid": rid}, namespace="/room")
        await sio.emit("rooms_occupancy", {"id": rid, "occupancy": occ}, namespace="/rooms")
        await sio.emit("member_joined", {"user_id": uid, "state": user_state}, room=f"room:{rid}", skip_sid=sid, namespace="/room")
        if applied:
            await sio.emit("state_changed", {"user_id": uid, **applied}, room=f"room:{rid}", skip_sid=sid, namespace="/room")

        lk_token = make_livekit_token(identity=str(uid), name=f"user-{uid}", room=str(rid))
        return {"ok": True, "room_id": rid, "token": lk_token, "snapshot": snapshot, "self_pref": user_state}

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
            return {"ok": False}

        r = get_redis()
        applied = await apply_state(r, rid, uid, data or {})
        if applied:
            await sio.emit("state_changed", {"user_id": uid, **applied}, room=f"room:{rid}", namespace="/room")

        return {"ok": True}

    except Exception:
        log.exception("sio.state.error", sid=sid)
        return {"ok": False}


@sio.event(namespace="/room")
async def disconnect(sid):
    try:
        sess = await sio.get_session(sid, namespace="/room")
        uid = int(sess["uid"])
        rid = int(sess.get("rid") or 0)
        if not rid:
            return

        r = get_redis()
        occ, gc_seq = await leave_room_atomic(r, rid, uid)

        await sio.leave_room(sid, f"room:{rid}", namespace="/room")
        await sio.emit("member_left", {"user_id": uid}, room=f"room:{rid}", namespace="/room")
        await sio.emit("rooms_occupancy", {"id": rid, "occupancy": occ}, namespace="/rooms")
        await sio.save_session(sid, {"uid": uid, "rid": None}, namespace="/room")

        if occ == 0:
            async def _gc():
                try:
                    removed = await gc_empty_room(rid, expected_seq=gc_seq)
                    if removed:
                        await sio.emit("rooms_remove", {"id": rid}, namespace="/rooms")
                except Exception:
                    log.exception("gc failed rid=%s", rid)
            asyncio.create_task(_gc())

    except Exception:
        log.exception("sio.disconnect.error", sid=sid)
