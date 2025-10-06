from __future__ import annotations
import structlog
from ..sio import sio
from ..utils import validate_auth

log = structlog.get_logger()


@sio.event(namespace="/auth")
async def connect(sid, environ, auth):
    vr = await validate_auth(auth)
    if not vr:
        log.warning("auth.connect.denied", sid=sid)
        return False

    uid, _ = vr
    log.info("auth.connect.ok", sid=sid, uid=uid)
    await sio.save_session(sid, {"uid": uid}, namespace="/auth")
    await sio.enter_room(sid, f"user:{uid}", namespace="/auth")


@sio.event(namespace="/auth")
async def disconnect(sid):
    log.info("auth.disconnect", sid=sid)
    return
