from __future__ import annotations
import structlog
from ..sio import sio
from ..utils import validate_auth
from ...core.clients import get_redis
from ...core.db import SessionLocal
from ...api.utils import touch_user_last_visit

log = structlog.get_logger()


@sio.event(namespace="/auth")
async def connect(sid, environ, auth):
    vr = await validate_auth(auth)
    if not vr:
        log.warning("auth.connect.denied", sid=sid)
        return False

    uid = vr[0]
    r = get_redis()
    try:
        await r.incr(f"online:user:{uid}")
        await r.sadd("online:users", str(uid))
    except Exception:
        log.warning("auth.connect.online_track_failed", uid=uid)
    try:
        async with SessionLocal() as s:
            await touch_user_last_visit(s, uid)
    except Exception:
        log.warning("auth.connect.last_visit_failed", uid=uid)
    await sio.save_session(sid,
                           {"uid": uid},
                           namespace="/auth")
    await sio.enter_room(sid,
                         f"user:{uid}",
                         namespace="/auth")


@sio.event(namespace="/auth")
async def disconnect(sid):
    try:
        sess = await sio.get_session(sid, namespace="/auth")
        uid = int(sess.get("uid") or 0)
    except Exception:
        uid = 0
    if not uid:
        return
    r = get_redis()
    try:
        cnt = int(await r.decr(f"online:user:{uid}") or 0)
    except Exception:
        cnt = 0
    if cnt <= 0:
        try:
            async with SessionLocal() as s:
                await touch_user_last_visit(s, uid)
        except Exception:
            log.warning("auth.disconnect.last_visit_failed", uid=uid)
        try:
            async with r.pipeline() as p:
                await p.delete(f"online:user:{uid}")
                await p.srem("online:users", str(uid))
                await p.execute()
        except Exception:
            log.warning("auth.disconnect.online_track_failed", uid=uid)
    return
