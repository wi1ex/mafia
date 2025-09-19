from __future__ import annotations
import time
import uuid
import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable, Awaitable
from ..core.security import decode_token


async def _logging_logic(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    client_ip = request.client.host if request.client else "-"
    user_id: int | None = None
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        try:
            p = decode_token(auth[7:].strip())
            if p.get("typ") == "access":
                user_id = int(p.get("sub") or 0) or None
        except Exception:
            user_id = None

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=rid,
        method=request.method,
        path=str(request.url.path),
        client_ip=client_ip,
        user_id=user_id,
    )
    log = structlog.get_logger()
    log.info("request.start")

    t0 = time.perf_counter()
    try:
        resp = await call_next(request)
    except Exception as exc:
        log.exception("request.error", error=str(exc))
        raise
    finally:
        duration_ms = (time.perf_counter() - t0) * 1000.0
        log.info("request.end", duration_ms=round(duration_ms, 2))

    resp.headers.setdefault("X-Request-ID", rid)
    resp.headers.setdefault("Server-Timing", f"app;dur={round(duration_ms, 2)}")
    return resp


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        return await _logging_logic(request, call_next)
