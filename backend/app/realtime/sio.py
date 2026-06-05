from __future__ import annotations
from importlib import import_module
import socketio
import structlog
from ..core.settings import settings

log = structlog.get_logger()

_ns_loaded = False
_redis_options = {
    "socket_connect_timeout": 3.0,
    "socket_timeout": None,
    "socket_keepalive": True,
    "health_check_interval": 10,
    "retry_on_timeout": True,
}

mgr = socketio.AsyncRedisManager(settings.redis_url, redis_options=_redis_options)
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
    import_module('app.realtime.namespaces.chat')
    _ns_loaded = True
