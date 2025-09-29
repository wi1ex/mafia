from __future__ import annotations
from typing import Any, Tuple
import socketio
import structlog
from jwt import ExpiredSignatureError
from ..core.clients import get_redis
from ..core.security import decode_token
from ..settings import settings

log = structlog.get_logger()

mgr = socketio.AsyncRedisManager(settings.redis_url)
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.BACKEND_CORS_ORIGINS,
    client_manager=mgr,
    logger=False,
    engineio_logger=False,
    ping_interval=25,
    ping_timeout=60,
    max_http_buffer_size=64 * 1024,
    allow_upgrades=False,
    http_compression=False,
)

from .namespaces import rooms as _ns_rooms
from .namespaces import room as _ns_room
from .namespaces import auth as _ns_auth


async def validate_auth(auth: Any) -> Tuple[int, str] | None:
    token = auth.get("token") if isinstance(auth, dict) else None
    if not token:
        log.warning("sio.connect.no_token")
        return None

    try:
        p = decode_token(token)
        uid = int(p["sub"])
        sid = str(p.get("sid") or "")
        cur = await get_redis().get(f"user:{uid}:sid")
        if not cur or cur != sid:
            log.warning("sio.connect.replaced_session")
            return None

        role = str(p.get("role") or "user")
        return uid, role

    except ExpiredSignatureError:
        log.warning("sio.connect.expired_token")
        return None

    except Exception:
        log.warning("sio.connect.bad_token")
        return None
