from __future__ import annotations
import time
from typing import Any, Dict
import socketio
import structlog
from ..core.clients import get_redis
from ..core.security import decode_token
from ..settings import settings


log = structlog.get_logger()


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
    logger=True, engineio_logger=True,  # временно
)


def _to01(v: Any) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"
    s = str(v).strip().lower()
    return "1" if s in {"1", "true", "on", "yes"} else "0"


async def _snapshot(r, rid: int) -> Dict[str, Dict[str, str]]:
    ids = await r.smembers("room:{rid}:members".format(rid=rid))
    out: Dict[str, Dict[str, str]] = {}
    for b in ids or []:
        uid = (b.decode() if isinstance(b, (bytes, bytearray)) else str(b))
        st = await r.hgetall("room:{rid}:user:{uid}:state".format(rid=rid, uid=uid))
        out[uid] = {(k.decode() if isinstance(k, (bytes, bytearray)) else k): (v.decode() if isinstance(v, (bytes, bytearray)) else v)
                    for k, v in (st or {}).items()}
    return out


async def _broadcast_rooms_occupancy(r, rid: int) -> None:
    occ = int(await r.scard("room:{rid}:members".format(rid=rid)) or 0)
    await sio.emit("rooms_occupancy", {"id": rid, "occupancy": occ})


async def _apply_state(r, rid: int, uid: int, data: Dict[str, Any]) -> Dict[str, str]:
    m = {}
    for k in ("mic", "cam", "speakers", "visibility"):
        if k in data:
            m[k] = _to01(data[k])
    if not m:
        return {}
    await r.hset("room:{rid}:user:{uid}:state".format(rid=rid, uid=uid), mapping=m)
    await r.hset("user:{uid}:last_state".format(uid=uid), mapping=m)
    return m


@sio.event
async def connect(sid, environ, auth):
    try:
        token = auth.get("token") if isinstance(auth, dict) else None
        if not token:
            raise ConnectionRefusedError("no_token")
        payload = decode_token(token)
        uid = int(payload.get("sub"))
        await sio.save_session(sid, {"uid": uid, "rid": None})
        log.info("sio.connect", sid=sid, uid=uid)
    except ConnectionRefusedError as e:
        log.warning("sio.connect.refused", reason=str(e))
        raise
    except Exception:
        log.exception("sio.connect.error")
        raise ConnectionRefusedError("bad_token")


@sio.event
async def join(sid, data):
    """
    Client → { room_id, state? }
    Server → snapshot + self_pref для инициализации бэйджей и локальных тумблеров
    """
    sess = await sio.get_session(sid)
    uid = int(sess["uid"])
    rid = int(data.get("room_id"))
    r = get_redis()

    await r.sadd("room:{rid}:members".format(rid=rid), uid)
    await r.set("room:{rid}:member:{uid}".format(rid=rid, uid=uid), str(int(time.time())))

    init_state = data.get("state") or {}
    if init_state:
        await _apply_state(r, rid, uid, init_state)

    await sio.enter_room(sid, f"room:{rid}")
    await sio.save_session(sid, {"uid": uid, "rid": rid})

    snap = await _snapshot(r, rid)
    self_pref_raw = await r.hgetall("user:{uid}:last_state".format(uid=uid))
    self_pref = {(k.decode() if isinstance(k, (bytes, bytearray)) else k): (v.decode() if isinstance(v, (bytes, bytearray)) else v)
                 for k, v in (self_pref_raw or {}).items()}

    await sio.emit("snapshot", snap, room=sid)
    await sio.emit("self_pref", self_pref, room=sid)
    await sio.emit("member_joined", {"user_id": uid}, room=f"room:{rid}", skip_sid=sid)
    await _broadcast_rooms_occupancy(r, rid)
    return {"ok": True}


@sio.event
async def state(sid, data):
    """ Client → { mic, cam, speakers, visibility }  Ack ← { ok: true } """
    sess = await sio.get_session(sid)
    uid = int(sess["uid"])
    rid = int(sess.get("rid") or 0)
    if not rid:
        return {"ok": False}
    r = get_redis()
    applied = await _apply_state(r, rid, uid, data or {})
    if applied:
        await sio.emit("state_changed", {"user_id": uid, **applied}, room=f"room:{rid}")
    return {"ok": True}


@sio.event
async def heartbeat(sid):
    sess = await sio.get_session(sid)
    uid = int(sess["uid"])
    rid = int(sess.get("rid") or 0)
    if not rid:
        return {"ok": False}
    r = get_redis()
    await r.set("room:{rid}:member:{uid}".format(rid=rid, uid=uid), str(int(time.time())))
    return {"ok": True}


async def _force_leave(sid):
    sess = await sio.get_session(sid)
    uid = int(sess["uid"])
    rid = int(sess.get("rid") or 0)
    if not rid:
        return
    r = get_redis()
    await r.srem("room:{rid}:members".format(rid=rid), uid)
    await r.delete("room:{rid}:member:{uid}".format(rid=rid, uid=uid))
    await r.delete("room:{rid}:user:{uid}:state".format(rid=rid, uid=uid))
    await sio.leave_room(sid, f"room:{rid}")
    await sio.emit("member_left", {"user_id": uid}, room=f"room:{rid}")
    await _broadcast_rooms_occupancy(r, rid)
    await sio.save_session(sid, {"uid": uid, "rid": None})


@sio.event
async def goodbye(sid, data=None):
    await _force_leave(sid)
    return {"ok": True}


@sio.event
async def disconnect(sid):
    try:
        await _force_leave(sid)
    except Exception:
        pass
    log.info("sio.disconnect", sid=sid)
