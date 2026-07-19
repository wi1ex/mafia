from __future__ import annotations
from importlib import import_module
import sys
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


def audit_sio_event_guards() -> None:
    protected_namespaces = {"/auth", "/chat", "/room", "/rooms"}
    exempt_events = {"connect", "disconnect"}
    for namespace, handlers in sio.handlers.items():
        if namespace not in protected_namespaces:
            continue
        for event, handler in handlers.items():
            if event in exempt_events:
                continue

            module = sys.modules.get(getattr(handler, "__module__", ""))
            current = getattr(module, getattr(handler, "__name__", ""), None) if module else None
            registered_guard = getattr(handler, "__sio_guard__", None)
            current_guard = getattr(current, "__sio_guard__", None)
            if not registered_guard or current is not handler:
                detail = current_guard or "missing rate_limited_sio"
                raise RuntimeError(
                    f"Socket.IO event {namespace}:{event} bypasses {detail}; "
                    "place @sio.event above @rate_limited_sio."
                )


def register_namespaces() -> None:
    global _ns_loaded
    if _ns_loaded:
        return

    import_module('app.realtime.namespaces.rooms')
    import_module('app.realtime.namespaces.room')
    import_module('app.realtime.namespaces.auth')
    import_module('app.realtime.namespaces.chat')
    audit_sio_event_guards()
    _ns_loaded = True
