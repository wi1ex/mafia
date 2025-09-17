from __future__ import annotations
import asyncio
from jwt import ExpiredSignatureError
from ..sio import sio
from ...core.clients import get_redis
from ...core.security import decode_token
from ..utils import snapshot, apply_state, broadcast_rooms_occupancy, gc_empty_room


@sio.event(namespace="/room")
async def connect(sid, environ, auth):
    try:
        token = auth.get("token") if isinstance(auth, dict) else None
        if not token:
            raise ConnectionRefusedError("no_token")
        uid = int(decode_token(token)["sub"])
        await sio.save_session(sid, {"uid": uid, "rid": None}, namespace="/room")
    except ExpiredSignatureError:
        raise ConnectionRefusedError("expired_token")
    except Exception:
        raise ConnectionRefusedError("bad_token")


@sio.event(namespace="/room")
async def join(sid, data):
    sess = await sio.get_session(sid, namespace="/room")
    uid = int(sess["uid"])
    rid = int(data.get("room_id"))
    r = get_redis()

    await r.sadd(f"room:{rid}:members", uid)

    applied = await apply_state(r, rid, uid, data.get("state") or {})
    await sio.enter_room(sid, f"room:{rid}", namespace="/room")
    await sio.save_session(sid, {"uid": uid, "rid": rid}, namespace="/room")

    snap = await snapshot(r, rid)
    self_pref = snap.get(str(uid), {})
    state_for_broadcast = {**self_pref, **applied} if applied else self_pref

    await sio.emit("snapshot", snap, room=sid, namespace="/room")
    await sio.emit("self_pref", self_pref, room=sid, namespace="/room")
    await sio.emit("member_joined", {"user_id": uid, "state": state_for_broadcast}, room=f"room:{rid}", skip_sid=sid, namespace="/room")
    if applied:
        await sio.emit("state_changed", {"user_id": uid, **applied}, room=f"room:{rid}", skip_sid=sid, namespace="/room")

    await broadcast_rooms_occupancy(r, rid)
    return {"ok": True}


@sio.event(namespace="/room")
async def state(sid, data):
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


async def _force_leave(sid):
    sess = await sio.get_session(sid, namespace="/room")
    uid = int(sess["uid"])
    rid = int(sess.get("rid") or 0)
    if not rid:
        return
    r = get_redis()
    await r.srem(f"room:{rid}:members", uid)
    await sio.leave_room(sid, f"room:{rid}", namespace="/room")
    await sio.emit("member_left", {"user_id": uid}, room=f"room:{rid}", namespace="/room")
    await broadcast_rooms_occupancy(r, rid)
    await sio.save_session(sid, {"uid": uid, "rid": None}, namespace="/room")
    if int(await r.scard(f"room:{rid}:members") or 0) == 0:
        asyncio.create_task(gc_empty_room(rid))


@sio.event(namespace="/room")
async def goodbye(sid):
    await _force_leave(sid)
    return {"ok": True}


@sio.event(namespace="/room")
async def disconnect(sid):
    try:
        await _force_leave(sid)
    finally:
        return
