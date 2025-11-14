from __future__ import annotations
import socketio
import structlog
from importlib import import_module
from ..core.settings import settings

log = structlog.get_logger()

_ns_loaded = False
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
    allow_upgrades=True,
    http_compression=True,
)

def register_namespaces() -> None:
    global _ns_loaded
    if _ns_loaded:
        return

    import_module('app.realtime.namespaces.rooms')
    import_module('app.realtime.namespaces.room')
    import_module('app.realtime.namespaces.auth')
    _ns_loaded = True
