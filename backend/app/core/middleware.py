from __future__ import annotations
import time
import uuid
import structlog
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy import update, func
from starlette.types import ASGIApp, Receive, Scope, Send, Message
from .clients import get_redis
from ..security.admin_guard import normalize_protected_admin_role
from ..security.auth_tokens import decode_token
from ..core.db import SessionLocal
from ..models.user import User
from ..services.user_cache import read_user_profile_cache

log = structlog.get_logger()

SECURITY_RESPONSE_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
)


def _append_header_if_missing(headers: list[tuple[bytes, bytes]], name: bytes, value: bytes) -> None:
    target = name.lower()
    for header_name, _ in headers:
        if header_name.lower() == target:
            return

    headers.append((name, value))


def _is_https_request(scope: Scope) -> bool:
    if str(scope.get("scheme") or "").lower() == "https":
        return True

    for key, value in (scope.get("headers") or []):
        if key == b"x-forwarded-proto":
            try:
                return value.decode().split(",", 1)[0].strip().lower() == "https"

            except Exception:
                return False

    return False


async def build_auth_log_context(auth_header: str) -> dict[str, object]:
    header = str(auth_header or "").strip()
    if not header:
        return {}

    if not header.lower().startswith("bearer "):
        return {"auth_status": "unsupported_scheme"}

    token = header[7:].strip()
    if not token:
        return {"auth_status": "missing_bearer_token"}

    try:
        payload = decode_token(token)
        token_type = str(payload.get("typ") or "")
        if token_type != "access":
            return {
                "auth_status": "bad_token_type",
                "auth_token_type": token_type,
            }

        uid = int(payload.get("sub") or 0)
        if uid <= 0:
            return {"auth_status": "bad_sub"}

        sid = str(payload.get("sid") or "")
        role_from_token = str(payload.get("role") or "user")
        role = role_from_token
        username = str(payload.get("username") or f"user{uid}")

        redis = get_redis()
        current_sid = await redis.get(f"user:{uid}:sid")
        if not sid or not current_sid or current_sid != sid:
            return {
                "auth_status": "sid_mismatch",
                "auth_token_user_id": uid,
            }

        profile = await read_user_profile_cache(uid, redis_client=redis)
        if profile:
            if profile.get("username"):
                username = str(profile["username"])
            if profile.get("role"):
                role = str(profile["role"])

        role = normalize_protected_admin_role(uid, role, fallback_role=role_from_token)

        return {
            "auth_status": "ok",
            "auth_user_id": uid,
            "auth_username": username,
            "auth_role": role,
        }

    except ExpiredSignatureError:
        return {"auth_status": "expired"}

    except InvalidTokenError as exc:
        return {
            "auth_status": "invalid",
            "auth_error": type(exc).__name__,
        }

    except Exception as exc:
        return {
            "auth_status": "auth_log_failed",
            "auth_error": type(exc).__name__,
        }


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)

        is_https = _is_https_request(scope)

        async def send_wrapper(message: Message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                for name, value in SECURITY_RESPONSE_HEADERS:
                    _append_header_if_missing(headers, name, value)
                if is_https:
                    _append_header_if_missing(headers, b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


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
        auth_header = _get("authorization")
        forwarded_for = _get("x-forwarded-for")
        real_ip = _get("x-real-ip")
        user_agent = _get("user-agent")
        client = scope.get("client") or ("", 0)
        client_host = str(client[0] or "")
        client_ip = (forwarded_for.split(",", 1)[0].strip() if forwarded_for else "") or real_ip or client_host

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=rid,
            method=scope.get("method"),
            path=scope.get("path"),
            client_ip=client_ip,
            forwarded_for=forwarded_for,
            user_agent=user_agent,
        )
        auth_ctx = await build_auth_log_context(auth_header)
        if auth_ctx:
            structlog.contextvars.bind_contextvars(**auth_ctx)

        log.info("request.start")
        t0 = time.perf_counter()
        headers_sent = False
        status_code: int | None = None

        async def send_wrapper(message: Message):
            nonlocal headers_sent, status_code
            if message["type"] == "http.response.start" and not headers_sent:
                status_code = int(message.get("status") or 0)
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
            log.info("request.end", duration_ms=round(dur_ms, 2), status_code=status_code)
            try:
                structlog.contextvars.clear_contextvars()
            except Exception as e:
                log.warning("request.clear_ctx_failed", err=type(e).__name__)


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
                                await s.execute(update(User).where(User.id == uid).values(last_visit_at=func.now()))
                                await s.commit()

            except ExpiredSignatureError:
                log.info("last_touch.failed", err="ExpiredSignatureError")
            except InvalidTokenError as e:
                log.info("last_touch.failed", err=type(e).__name__)
            except Exception as e:
                log.warning("last_touch.failed", err=type(e).__name__)

        return await self.app(scope, receive, send)
