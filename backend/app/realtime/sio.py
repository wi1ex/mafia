from __future__ import annotations
import socketio
from ..settings import settings

mgr = socketio.AsyncRedisManager(settings.redis_url)
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.BACKEND_CORS_ORIGINS or "*",
    client_manager=mgr,
)

from .namespaces import rooms as _ns_rooms
from .namespaces import room as _ns_room
