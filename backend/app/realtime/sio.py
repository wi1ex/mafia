from __future__ import annotations
import socketio
from ..settings import settings

mgr = socketio.AsyncRedisManager(settings.redis_url)
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.BACKEND_CORS_ORIGINS,
    client_manager=mgr,
    logger=False,
    engineio_logger=False,
    ping_timeout=25,
    ping_interval=30,
    max_http_buffer_size=64 * 1024,
    allow_upgrades=False,
    http_compression=False,
)

from .namespaces import rooms as _ns_rooms
from .namespaces import room as _ns_room
