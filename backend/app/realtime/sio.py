from __future__ import annotations
import socketio
from ..settings import settings

def _redis_url() -> str:
    host = getattr(settings, "REDIS_HOST", "localhost")
    port = getattr(settings, "REDIS_PORT", 6379)
    pwd  = getattr(settings, "REDIS_PASSWORD", "")
    auth = f":{pwd}@" if pwd else ""
    return f"redis://{auth}{host}:{port}/0"

mgr = socketio.AsyncRedisManager(_redis_url())
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.BACKEND_CORS_ORIGINS or "*",
    client_manager=mgr,
)

from .namespaces import rooms as _ns_rooms
from .namespaces import room as _ns_room
