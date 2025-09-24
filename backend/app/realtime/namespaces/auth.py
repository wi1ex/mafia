from __future__ import annotations
from jwt import ExpiredSignatureError
import structlog
from ..sio import sio
from ...core.security import decode_token
from ...core.clients import get_redis

log = structlog.get_logger()


@sio.event(namespace="/auth")
async def connect(sid, environ, auth):
    try:
        token = auth.get("token") if isinstance(auth, dict) else None
        if not token:
            log.warning("sio.connect.no_token")
            return False

        p = decode_token(token)
        uid = int(p["sub"])
        cur = await get_redis().get(f"user:{uid}:sid")
        tok_sid = (p.get("sid") or "")
        if not cur or cur != tok_sid:
            log.warning("sio.connect.replaced_session")
            return False

        await sio.save_session(sid, {"uid": uid}, namespace="/auth")
        await sio.enter_room(sid, f"user:{uid}", namespace="/auth")
    except ExpiredSignatureError:
        log.warning("sio.connect.expired_token")
        return False
    except Exception:
        log.warning("sio.connect.bad_token")
        return False


@sio.event(namespace="/auth")
async def disconnect(sid):
    return
