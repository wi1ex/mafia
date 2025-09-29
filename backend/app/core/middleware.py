from __future__ import annotations
import time
import uuid
import structlog
from starlette.types import ASGIApp, Receive, Scope, Send, Message


class LoggingMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)

        def _get(h: str) -> str:
            hb = h.encode()
            for k, v in headers:
                if k == hb:
                    try:
                        return v.decode()
                    except Exception:
                        return ""
            return ""

        headers = scope.get("headers") or []
        rid = _get("x-request-id") or uuid.uuid4().hex

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=rid,
            method=scope.get("method"),
            path=scope.get("path"),
        )

        log = structlog.get_logger()
        log.info("request.start")

        t0 = time.perf_counter()
        headers_sent = False

        async def send_wrapper(message: Message):
            nonlocal headers_sent
            if message["type"] == "http.response.start" and not headers_sent:
                out = list(message.get("headers") or [])
                out.append((b"x-request-id", rid.encode()))
                dur = round((time.perf_counter() - t0) * 1000.0, 2)
                out.append((b"server-timing", f"app;dur={dur}".encode()))
                message["headers"] = out
                headers_sent = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            log.exception("request.error", error=str(exc))
            raise
        finally:
            dur_ms = (time.perf_counter() - t0) * 1000.0
            log.info("request.end", duration_ms=round(dur_ms, 2))
            try:
                structlog.contextvars.clear_contextvars()
            except Exception:
                pass
