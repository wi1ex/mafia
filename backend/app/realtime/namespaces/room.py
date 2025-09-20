from __future__ import annotations
import asyncio
from jwt import ExpiredSignatureError
from sqlalchemy.ext.asyncio import async_sessionmaker
from ...db import engine
from ...models.room import Room
from ...models.user import User
from ..sio import sio
from ...core.clients import get_redis
from ...core.security import decode_token
from ...schemas import JoinAck
from ...services.livekit_tokens import make_livekit_token
from ...utils import apply_state, gc_empty_room, get_room_snapshot

_sessionmaker = async_sessionmaker(bind=engine, expire_on_commit=False)

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
async def join(sid, data) -> JoinAck:
    sess = await sio.get_session(sid, namespace="/room")
    uid = int(sess["uid"])
    rid = int(data.get("room_id") or 0)
    if not rid:
        return {"ok": False, "error": "bad_room_id", "status": 400}

    r = get_redis()
    async with _sessionmaker() as s:
        room = await s.get(Room, rid)
        if room is None:
            return {"ok": False, "error": "room_not_found", "status": 404}

        is_member = await r.sismember(f"room:{rid}:members", str(uid))
        if not is_member:
            occ = int(await r.scard(f"room:{rid}:members") or 0)
            if occ >= room.user_limit:
                return {"ok": False, "error": "room_is_full", "status": 409}
            await r.sadd(f"room:{rid}:members", str(uid))

        snapshot = await get_room_snapshot(r, rid)
        self_pref = snapshot.get(str(uid), {})
        user = await s.get(User, uid)
        lk_token = make_livekit_token(identity=str(uid), name=(user.username or f"user-{uid}"), room=str(rid))

    applied = await apply_state(r, rid, uid, data.get("state") or {})
    if applied:
        prev = snapshot.get(str(uid), {}) or {}
        snapshot[str(uid)] = {**prev, **applied}
        self_pref = {**(self_pref or {}), **applied}

    await sio.enter_room(sid, f"room:{rid}", namespace="/room")
    await sio.save_session(sid, {"uid": uid, "rid": rid}, namespace="/room")
    occ = int(await r.scard(f"room:{rid}:members") or 0)
    await sio.emit("rooms_occupancy", {"id": rid, "occupancy": occ}, namespace="/rooms")

    state_for_broadcast = {**(snapshot.get(str(uid), {})), **applied} if applied else snapshot.get(str(uid), {})
    await sio.emit("member_joined", {"user_id": uid, "state": state_for_broadcast}, room=f"room:{rid}", skip_sid=sid, namespace="/room")
    if applied:
        await sio.emit("state_changed", {"user_id": uid, **applied}, room=f"room:{rid}", skip_sid=sid, namespace="/room")

    return {"ok": True, "room_id": rid, "token": lk_token, "snapshot": snapshot, "self_pref": self_pref or {}}


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


@sio.event(namespace="/room")
async def disconnect(sid):
    sess = await sio.get_session(sid, namespace="/room")
    uid = int(sess["uid"])
    rid = int(sess.get("rid") or 0)
    if not rid:
        return

    r = get_redis()
    await r.srem(f"room:{rid}:members", str(uid))
    await sio.leave_room(sid, f"room:{rid}", namespace="/room")
    await sio.emit("member_left", {"user_id": uid}, room=f"room:{rid}", namespace="/room")
    occ = int(await r.scard(f"room:{rid}:members") or 0)
    await sio.emit("rooms_occupancy", {"id": rid, "occupancy": occ}, namespace="/rooms")
    await sio.save_session(sid, {"uid": uid, "rid": None}, namespace="/room")

    if int(await r.scard(f"room:{rid}:members") or 0) == 0:
        async def _gc():
            removed = await gc_empty_room(rid)
            if removed:
                await sio.emit("rooms_remove", {"id": rid}, namespace="/rooms")
        asyncio.create_task(_gc())
