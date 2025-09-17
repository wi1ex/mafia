from __future__ import annotations
import asyncio
from typing import Any, Dict
import socketio
import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker
from ..db import engine
from ..core.clients import get_redis
from ..core.security import decode_token
from ..models.room import Room
from ..settings import settings


log = structlog.get_logger()
_sessionmaker = async_sessionmaker(bind=engine, expire_on_commit=False)


def _redis_url() -> str:
    host = getattr(settings, "REDIS_HOST", "localhost")
    port = getattr(settings, "REDIS_PORT", 6379)
    pwd = getattr(settings, "REDIS_PASSWORD", "")
    auth = f":{pwd}@" if pwd else ""
    return f"redis://{auth}{host}:{port}/0"


mgr = socketio.AsyncRedisManager(_redis_url())
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.BACKEND_CORS_ORIGINS or "*",
    client_manager=mgr,
)


async def _broadcast_rooms_occupancy(r, rid: int) -> None:
    occ = int(await r.scard(f"room:{rid}:members") or 0)
    await sio.emit("rooms_occupancy", {"id": rid, "occupancy": occ}, namespace="/rooms")


async def _gc_empty_room(rid: int):
    r = get_redis()
    if not await r.setnx(f"room:{rid}:gc_lock", "1"):
        return
    await r.expire(f"room:{rid}:gc_lock", 20)

    await asyncio.sleep(10)
    occ = int(await r.scard(f"room:{rid}:members") or 0)
    if occ > 0:
        return

    await r.delete(f"room:{rid}:params")
    await r.srem("rooms:index", rid)

    async with _sessionmaker() as s:
        rm = await s.get(Room, rid)
        if rm:
            await s.delete(rm)
            await s.commit()

    await sio.emit("rooms_remove", {"id": rid}, namespace="/rooms")


def _to01(v: Any) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"
    s = str(v).strip().lower()
    return "1" if s in {"1", "true", "on", "yes"} else "0"


async def _snapshot(r, rid: int) -> Dict[str, Dict[str, str]]:
    ids = await r.smembers(f"room:{rid}:members")
    out: Dict[str, Dict[str, str]] = {}
    for b in ids or []:
        uid = (b.decode() if isinstance(b, (bytes, bytearray)) else str(b))
        st = await r.hgetall(f"room:{rid}:user:{uid}:state")
        out[uid] = {(k.decode() if isinstance(k, (bytes, bytearray)) else k): (v.decode() if isinstance(v, (bytes, bytearray)) else v)
                    for k, v in (st or {}).items()}
    return out


async def _apply_state(r, rid: int, uid: int, data: Dict[str, Any]) -> Dict[str, str]:
    m = {}
    for k in ("mic", "cam", "speakers", "visibility"):
        if k in data:
            m[k] = _to01(data[k])
    if not m:
        return {}
    await r.hset(f"room:{rid}:user:{uid}:state", mapping=m)
    await r.hset(f"room:{rid}:user:{uid}:last_state", mapping=m)
    return m


# ---------- PUBLIC namespace: /rooms
@sio.event(namespace="/rooms")
async def connect(sid, environ, auth):
    pass


# ---------- PRIVATE namespace: /room
@sio.event(namespace="/room")
async def connect(sid, environ, auth):
    try:
        token = auth.get("token") if isinstance(auth, dict) else None
        if not token:
            raise ConnectionRefusedError("no_token")
        payload = decode_token(token)
        uid = int(payload.get("sub"))
        await sio.save_session(sid, {"uid": uid, "rid": None}, namespace="/room")
        log.info("sio.connect", sid=sid, uid=uid)
    except ConnectionRefusedError as e:
        log.warning("sio.connect.refused", reason=str(e))
        raise
    except Exception:
        log.exception("sio.connect.error")
        raise ConnectionRefusedError("bad_token")


@sio.event(namespace="/room")
async def join(sid, data):
    sess = await sio.get_session(sid, namespace="/room")
    uid = int(sess["uid"])
    rid = int(data.get("room_id"))
    r = get_redis()

    await r.sadd(f"room:{rid}:members", uid)

    init_state = data.get("state") or {}
    applied = {}
    if init_state:
        applied = await _apply_state(r, rid, uid, init_state)

    await sio.enter_room(sid, f"room:{rid}", namespace="/room")
    await sio.save_session(sid, {"uid": uid, "rid": rid}, namespace="/room")

    snap = await _snapshot(r, rid)
    self_pref_raw = await r.hgetall(f"room:{rid}:user:{uid}:last_state")
    self_pref = {(k.decode() if isinstance(k, (bytes, bytearray)) else k): (v.decode() if isinstance(v, (bytes, bytearray)) else v)
                 for k, v in (self_pref_raw or {}).items()}
    cur_state_raw = await r.hgetall(f"room:{rid}:user:{uid}:state")
    cur_state = {(k.decode() if isinstance(k, (bytes, bytearray)) else k): (v.decode() if isinstance(v, (bytes, bytearray)) else v)
                 for k, v in (cur_state_raw or {}).items()}

    await sio.emit("snapshot", snap, room=sid, namespace="/room")
    await sio.emit("self_pref", self_pref, room=sid, namespace="/room")
    await sio.emit("member_joined", {"user_id": uid, "state": cur_state}, room=f"room:{rid}", skip_sid=sid, namespace="/room")

    if applied:
        await sio.emit("state_changed", {"user_id": uid, **applied}, room=f"room:{rid}", skip_sid=sid, namespace="/room")

    await _broadcast_rooms_occupancy(r, rid)
    return {"ok": True}


@sio.event(namespace="/room")
async def state(sid, data):
    sess = await sio.get_session(sid, namespace="/room")
    uid = int(sess["uid"])
    rid = int(sess.get("rid") or 0)
    if not rid:
        return {"ok": False}
    r = get_redis()
    applied = await _apply_state(r, rid, uid, data or {})
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
    await r.delete(f"room:{rid}:user:{uid}:state")
    await sio.leave_room(sid, f"room:{rid}", namespace="/room")
    await sio.emit("member_left", {"user_id": uid}, room=f"room:{rid}", namespace="/room")
    await _broadcast_rooms_occupancy(r, rid)
    await sio.save_session(sid, {"uid": uid, "rid": None}, namespace="/room")
    if int(await r.scard(f"room:{rid}:members") or 0) == 0:
        asyncio.create_task(_gc_empty_room(rid))


@sio.event(namespace="/room")
async def goodbye(sid):
    await _force_leave(sid)
    return {"ok": True}


@sio.event(namespace="/room")
async def disconnect(sid):
    await _force_leave(sid)
    log.info("sio.disconnect", sid=sid)
