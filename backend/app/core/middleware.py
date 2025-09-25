from __future__ import annotations
import time
import uuid
import structlog
from ..core.security import decode_token
from starlette.types import ASGIApp, Receive, Scope, Send


class LoggingMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = dict(scope.get("headers") or [])

        def _get(h: str) -> str:
            return headers.get(h.encode(), b"").decode()

        rid = _get("x-request-id") or uuid.uuid4().hex
        client = scope.get("client")
        client_ip = client[0] if client else "-"
        user_id = None
        auth = _get("authorization")
        if auth and auth.lower().startswith("bearer "):
            try:
                p = decode_token(auth[7:].strip())
                if p.get("typ") == "access":
                    user_id = int(p.get("sub") or 0) or None
            except Exception:
                user_id = None

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=rid,
            method=scope.get("method"),
            path=scope.get("path"),
            client_ip=client_ip,
            user_id=user_id,
        )
        log = structlog.get_logger()
        log.info("request.start")

        t0 = time.perf_counter()
        sent = {"headers_sent": False}

        async def send_wrapper(message):
            if message["type"] == "http.response.start" and not sent["headers_sent"]:
                headers_list = list(message.get("headers") or [])
                headers_list.append((b"x-request-id", rid.encode()))
                duration = round((time.perf_counter() - t0) * 1000.0, 2)
                headers_list.append((b"server-timing", f"app;dur={duration}".encode()))
                message["headers"] = headers_list
                sent["headers_sent"] = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            log.exception("request.error", error=str(exc))
            raise
        finally:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            log.info("request.end", duration_ms=round(duration_ms, 2))
