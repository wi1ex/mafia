from __future__ import annotations
import time
import uuid
import structlog
from sqlalchemy import update, func
from starlette.types import ASGIApp, Receive, Scope, Send, Message
from .clients import get_redis
from .security import decode_token
from ..db import SessionLocal
from ..models.user import User


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


class LastLoginTouchMiddleware:
    def __init__(self, app: ASGIApp, *, ttl_s: int = 300, api_prefix: str = "/api"):
        self.app = app
        self.ttl_s = ttl_s
        self.api_prefix = api_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)

        method = (scope.get("method") or "").upper()
        path = scope.get("path") or ""

        if method == "OPTIONS" or not (path == self.api_prefix or path.startswith(self.api_prefix + "/")):
            return await self.app(scope, receive, send)

        auth = ""
        for k, v in (scope.get("headers") or []):
            if k == b"authorization":
                try:
                    auth = v.decode()
                except Exception:
                    auth = ""
                break

        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
            try:
                p = decode_token(token)
                if p.get("typ") == "access":
                    r = get_redis()
                    uid = int(p["sub"])
                    sid = str(p.get("sid") or "")
                    cur = await r.get(f"user:{uid}:sid")
                    if cur and cur == sid:
                        if await r.set(f"user:{uid}:last_touch", "1", ex=self.ttl_s, nx=True):
                            async with SessionLocal() as s:
                                await s.execute(update(User).where(User.id == uid).values(last_login_at=func.now()))
                                await s.commit()
            except Exception:
                pass

        return await self.app(scope, receive, send)
