from __future__ import annotations
import structlog
from ..sio import sio
from ..utils import validate_auth

log = structlog.get_logger()


@sio.event(namespace="/auth")
async def connect(sid, environ, auth):
    vr = await validate_auth(auth)
    if not vr:
        return False

    uid, _ = vr
    await sio.save_session(sid, {"uid": uid}, namespace="/auth")
    await sio.enter_room(sid, f"user:{uid}", namespace="/auth")


@sio.event(namespace="/auth")
async def disconnect(sid):
    return
