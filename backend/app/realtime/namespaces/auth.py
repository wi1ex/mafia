from __future__ import annotations
import structlog
from ..sio import sio
from ..utils import validate_auth
from ...core.clients import get_redis
from ...core.db import SessionLocal
from ...core.settings import settings
from ...api.utils import touch_user_last_visit, touch_user_online, check_sanctions_expired

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
        await touch_user_online(r, uid)
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
async def online_ping(sid, data=None):
    try:
        sess = await sio.get_session(sid, namespace="/auth")
        uid = int(sess.get("uid") or 0)
    except Exception:
        uid = 0

    if not uid:
        return

    r = get_redis()
    try:
        await touch_user_online(r, uid)
    except Exception:
        log.warning("auth.ping.online_track_failed", uid=uid)
    try:
        if await r.set(f"user:{uid}:last_visit_touch", "1", ex=settings.ONLINE_TTL_SECONDS, nx=True):
            async with SessionLocal() as s:
                await touch_user_last_visit(s, uid)
    except Exception:
        log.warning("auth.ping.last_visit_failed", uid=uid)
    try:
        await check_sanctions_expired(uid)
    except Exception:
        log.warning("auth.ping.sanctions_check_failed", uid=uid)


@sio.event(namespace="/auth")
async def disconnect(sid):
    try:
        sess = await sio.get_session(sid, namespace="/auth")
        uid = int(sess.get("uid") or 0)
    except Exception:
        uid = 0

    if not uid:
        return

    try:
        async with SessionLocal() as s:
            await touch_user_last_visit(s, uid)
    except Exception:
        log.warning("auth.disconnect.last_visit_failed", uid=uid)

    return
