from __future__ import annotations
import asyncio
import functools
import inspect
import ipaddress
import sys
import structlog
from typing import Any, Callable, Awaitable, Union, Optional, cast
from jwt import ExpiredSignatureError, InvalidTokenError
from fastapi import HTTPException, Depends, APIRouter, Request
from fastapi.routing import APIRoute
from ..core.clients import get_redis
from ..security.admin_guard import get_protected_admin_user_id, is_protected_admin_uid
from ..security.auth_tokens import get_identity, decode_token, parse_refresh_token
from ..realtime.sio import sio
from ..schemas.common import Identity

log = structlog.get_logger()

KeyBuilder = Callable[..., str]
RateLimitRules = tuple[tuple[int, int], ...]
SAFE_HTTP_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
PRIVILEGED_HTTP_PREFIXES = ("/api/admin", "/api/moderation")
PRIVILEGED_ALERT_WINDOW_S = 300
PRIVILEGED_SAFE_HTTP_LIMITS: RateLimitRules = ((15, 1), (90, 60))
NON_PRIVILEGED_ROUTE_PATHS = frozenset({"/api/admin/settings/public"})
CONTENT_SAFE_ROUTE_PATHS = frozenset({
    "/api/admin/settings/public",
    "/api/media/presign",
    "/api/rooms/{room_id}/info",
})
AUTH_ROUTE_LIMITS: dict[str, RateLimitRules] = {
    "/api/auth/login": ((3, 10), (8, 60)),
    "/api/auth/register": ((3, 30), (8, 60)),
    "/api/auth/refresh": ((7, 10), (24, 60)),
    "/api/auth/logout": ((5, 10), (20, 60)),
}
PUBLIC_SAFE_ROUTE_LIMITS: dict[str, RateLimitRules] = {
    "/api/admin/settings/public": ((30, 1), (120, 60)),
    "/api/media/presign": ((120, 1), (600, 60)),
    "/api/rooms/{room_id}/info": ((100, 1), (300, 60)),
}
DEFAULT_SAFE_HTTP_LIMITS: RateLimitRules = ((25, 1), (120, 60))
DEFAULT_MUTATING_HTTP_LIMITS: RateLimitRules = ((8, 1), (30, 60))
ACTOR_AUTH_HTTP_LIMITS: RateLimitRules = ((8, 10), (20, 60))
ACTOR_BOT_HTTP_LIMITS: RateLimitRules = ((30, 1), (120, 60))
ACTOR_CONTENT_HTTP_LIMITS: RateLimitRules = ((120, 1), (600, 60))
ACTOR_SAFE_HTTP_LIMITS: RateLimitRules = ((30, 1), (180, 60))
ACTOR_MUTATING_HTTP_LIMITS: RateLimitRules = ((10, 1), (30, 60))
AUTO_BLOCK_IP_VIOLATION_LIMIT = 8
AUTO_BLOCK_IP_WINDOW_S = 300
AUTO_BLOCK_IP_TTL_S = 1800
AUTO_BLOCK_IP_VIOLATION_DEDUPE_TTL_S = 60
PRIVILEGED_SENSITIVE_MUTATION_LIMITS: dict[str, int] = {
    "/api/admin/settings": 6,
    "/api/admin/rooms/{room_id}/close": 6,
    "/api/admin/rooms/kick": 5,
    "/api/admin/chat/clear": 2,
    "/api/admin/users/{user_id}/role": 4,
    "/api/admin/users/{user_id}/delete": 4,
    "/api/admin/users/{user_id}/restore": 4,
    "/api/admin/users/{user_id}/unverify": 4,
    "/api/admin/users/{user_id}/password_clear": 4,
    "/api/admin/users/{user_id}/timeout": 5,
    "/api/admin/users/{user_id}/ban": 5,
    "/api/admin/users/{user_id}/suspend": 5,
    "/api/moderation/rooms/{room_id}/close": 6,
    "/api/moderation/users/{user_id}/avatar_delete": 4,
    "/api/moderation/users/{user_id}/nickname_reset": 4,
    "/api/moderation/users/{user_id}/timeout": 5,
    "/api/moderation/users/{user_id}/suspend": 5,
}


def _mark_route_guard(wrapper: Callable[..., Any], guard_name: str) -> None:
    setattr(wrapper, "__route_guard__", guard_name)


def _ensure_identity_has_roles(ident: Identity | None, roles: tuple[str, ...]) -> Identity:
    if not ident:
        log.warning("require_roles.missing_identity")
        raise HTTPException(status_code=401, detail="Unauthorized")

    if roles and ident["role"] not in roles:
        log.warning("require_roles.forbidden", role=ident["role"], need=roles)
        raise HTTPException(status_code=403, detail="forbidden")

    return ident


def audit_router_guards(router: APIRouter) -> None:
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue

        endpoint = cast(Any, route.endpoint)
        module = sys.modules.get(endpoint.__module__)
        if module is None:
            continue

        current = getattr(module, endpoint.__name__, None)
        wrapper_name = getattr(current, "__route_guard__", None)
        if not wrapper_name or current is endpoint:
            continue

        methods = ",".join(sorted((route.methods or set()) - {"HEAD"})) or ",".join(sorted(route.methods or []))
        raise RuntimeError(
            f"Wrapped route {methods} {route.path} in {endpoint.__module__}.{endpoint.__name__} "
            f"was registered before {wrapper_name}; move @router.* above route decorators."
        )


def log_route(name: str):
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def wrap(*a, **kw):
                lg = structlog.get_logger().bind(route=name)
                lg.info("route.start")

                try:
                    res = await fn(*a, **kw)
                    lg.info("route.end")
                    return res

                except HTTPException:
                    raise

                except Exception:
                    lg.exception("route.error")
                    raise

            _mark_route_guard(wrap, "log_route")
            return wrap

        else:
            @functools.wraps(fn)
            def wrap_sync(*a, **kw):
                lg = structlog.get_logger().bind(route=name)
                lg.info("route.start")

                try:
                    res = fn(*a, **kw)
                    lg.info("route.end")
                    return res

                except HTTPException:
                    raise

                except Exception:
                    lg.exception("route.error")
                    raise

            _mark_route_guard(wrap_sync, "log_route")
            return wrap_sync

    return deco


def require_roles_deco(*roles: str):
    def deco(fn):
        if not asyncio.iscoroutinefunction(fn):
            raise TypeError("require_roles_deco может оборачивать только async-функции")

        sig = inspect.signature(fn)
        need_inject = "ident" not in sig.parameters

        @functools.wraps(fn)
        async def wrap(*args, **kwargs):
            _ensure_identity_has_roles(kwargs.get("ident"), roles)
            return await fn(*args, **kwargs)

        if need_inject:
            params = list(sig.parameters.values()) + [inspect.Parameter("ident", kind=inspect.Parameter.KEYWORD_ONLY, default=Depends(get_identity))]
            wrap.__signature__ = sig.replace(parameters=params)
        else:
            wrap.__signature__ = sig

        _mark_route_guard(wrap, "require_roles_deco")
        return wrap

    return deco


def require_roles_dep(*roles: str):
    async def dep(ident: Identity = Depends(get_identity)) -> Identity:
        return _ensure_identity_has_roles(ident, roles)

    return dep


def _ensure_identity_is_protected_admin(ident: Identity | None) -> Identity:
    ident = _ensure_identity_has_roles(ident, ("admin",))
    uid = int(ident["id"])
    if not is_protected_admin_uid(uid):
        log.warning(
            "require_protected_admin.forbidden",
            uid=uid,
            protected_admin_user_id=get_protected_admin_user_id(),
        )
        raise HTTPException(status_code=403, detail="forbidden")

    return ident


async def require_protected_admin_dep(ident: Identity = Depends(get_identity)) -> Identity:
    return _ensure_identity_is_protected_admin(ident)


def _extract_rate_limit_uid(auth_header: str) -> int | None:
    header = str(auth_header or "").strip()
    if not header.lower().startswith("bearer "):
        return None

    token = header[7:].strip()
    if not token:
        return None

    try:
        payload = decode_token(token)
        if str(payload.get("typ") or "") != "access":
            return None

        uid = int(payload.get("sub") or 0)
        return uid if uid > 0 else None

    except (ExpiredSignatureError, InvalidTokenError, ValueError, TypeError):
        return None

    except Exception:
        return None


def _request_client_ip(request: Request) -> str:
    forwarded_for = str(request.headers.get("x-forwarded-for") or "").strip()
    real_ip = str(request.headers.get("x-real-ip") or "").strip()
    client_host = str((request.client.host if request.client else "") or "").strip()
    return (forwarded_for.split(",", 1)[0].strip() if forwarded_for else "") or real_ip or client_host or "unknown"


def _extract_blockable_ip(request: Request) -> str | None:
    raw_ip = _request_client_ip(request)
    if not raw_ip or raw_ip == "unknown":
        return None

    try:
        return raw_ip if ipaddress.ip_address(raw_ip).is_global else None
    except ValueError:
        return None


def _extract_rate_limit_actor(request: Request) -> str:
    uid = _extract_rate_limit_uid(str(request.headers.get("authorization") or ""))
    if uid is not None:
        return f"user:{uid}"

    request_path = str(request.url.path or "").rstrip("/") or "/"
    if request_path in {"/api/auth/refresh", "/api/auth/logout"}:
        raw_refresh = str(request.cookies.get("rt") or "")
        if raw_refresh:
            ok, _, sid, _ = parse_refresh_token(raw_refresh)
            if ok and sid:
                return f"sid:{sid}"

    return f"ip:{_request_client_ip(request)}"


def _is_privileged_route(path: str) -> bool:
    normalized_path = str(path or "").rstrip("/") or "/"
    if normalized_path in NON_PRIVILEGED_ROUTE_PATHS:
        return False

    return any(normalized_path.startswith(prefix) for prefix in PRIVILEGED_HTTP_PREFIXES)


def _default_http_rate_limits(method: str, path: str) -> RateLimitRules:
    normalized_path = str(path or "/").rstrip("/") or "/"

    auth_limits = AUTH_ROUTE_LIMITS.get(normalized_path)
    if auth_limits is not None:
        return auth_limits

    public_safe_limits = PUBLIC_SAFE_ROUTE_LIMITS.get(normalized_path)
    if public_safe_limits is not None:
        return public_safe_limits

    if normalized_path.startswith("/api/bot"):
        return ((30, 1), (90, 60))

    if _is_privileged_route(normalized_path):
        if method in SAFE_HTTP_METHODS:
            return PRIVILEGED_SAFE_HTTP_LIMITS

        if normalized_path in PRIVILEGED_SENSITIVE_MUTATION_LIMITS:
            return ((2, 10), (PRIVILEGED_SENSITIVE_MUTATION_LIMITS[normalized_path], 60))

        return ((4, 10), (10, 60))

    return DEFAULT_SAFE_HTTP_LIMITS if method in SAFE_HTTP_METHODS else DEFAULT_MUTATING_HTTP_LIMITS


def _actor_http_rate_limit(method: str, path: str) -> tuple[str, RateLimitRules]:
    normalized_path = str(path or "/").rstrip("/") or "/"

    if normalized_path.startswith("/api/bot"):
        return "bot", ACTOR_BOT_HTTP_LIMITS

    if normalized_path.startswith("/api/auth"):
        return "auth", ACTOR_AUTH_HTTP_LIMITS

    if normalized_path in CONTENT_SAFE_ROUTE_PATHS:
        return "content", ACTOR_CONTENT_HTTP_LIMITS

    if method in SAFE_HTTP_METHODS:
        return "safe", ACTOR_SAFE_HTTP_LIMITS

    return "mutating", ACTOR_MUTATING_HTTP_LIMITS


async def _increase_rate_limit_counter(redis_client, *, key: str, window_s: int) -> int:
    created = await redis_client.set(key, 1, ex=window_s, nx=True)
    count = 1 if created else int(await redis_client.incr(key))
    if count == 1 and not created:
        try:
            await redis_client.expire(key, window_s)
        except Exception as exc:
            log.warning("http.rate_limit.expire_failed", key=key, window_s=window_s, err=type(exc).__name__)
    return count


async def _ensure_ip_not_blocked(redis_client, *, ip: str, method: str, path: str) -> None:
    block_key = f"rl:http:ip:block:{ip}"
    try:
        ttl = int(await redis_client.ttl(block_key))
    except Exception:
        ttl = -2

    if ttl and ttl > 0:
        log.warning(
            "security.ip_auto_block_hit",
            ip=ip,
            method=method,
            path=path,
            ttl=ttl,
        )
        raise HTTPException(
            status_code=429,
            detail="ip_temporarily_blocked",
            headers={"Retry-After": str(ttl)},
        )


async def _register_ip_violation(redis_client, *, ip: str, method: str, path: str, reason: str) -> None:
    dedupe_key = f"rl:http:ip:violation_seen:{ip}:{reason}:{method}:{path}"
    try:
        should_count = await redis_client.set(dedupe_key, 1, ex=AUTO_BLOCK_IP_VIOLATION_DEDUPE_TTL_S, nx=True)
    except Exception as exc:
        should_count = True
        log.warning(
            "security.ip_auto_block_violation_dedupe_failed",
            ip=ip,
            method=method,
            path=path,
            reason=reason,
            err=type(exc).__name__,
        )

    if not should_count:
        return

    violation_key = f"rl:http:ip:violations:{ip}"
    count = await _increase_rate_limit_counter(redis_client, key=violation_key, window_s=AUTO_BLOCK_IP_WINDOW_S)
    if count < AUTO_BLOCK_IP_VIOLATION_LIMIT:
        return

    block_key = f"rl:http:ip:block:{ip}"
    created = await redis_client.set(block_key, reason, ex=AUTO_BLOCK_IP_TTL_S, nx=True)
    if created:
        log.warning(
            "security.ip_auto_blocked",
            ip=ip,
            method=method,
            path=path,
            reason=reason,
            trigger_count=count,
            trigger_window_s=AUTO_BLOCK_IP_WINDOW_S,
            block_ttl_s=AUTO_BLOCK_IP_TTL_S,
            dedupe_ttl_s=AUTO_BLOCK_IP_VIOLATION_DEDUPE_TTL_S,
        )


async def _enforce_rate_limit_rules(redis_client, *, base_key: str, rules: RateLimitRules, method: str, path: str, actor: str, log_event: str, extra_fields: dict[str, object] | None = None) -> tuple[bool, int]:
    for limit, window_s in rules:
        scoped_key = f"{base_key}:w{window_s}"
        count = await _increase_rate_limit_counter(redis_client, key=scoped_key, window_s=window_s)
        if count <= limit:
            continue

        try:
            ttl = int(await redis_client.ttl(scoped_key))
        except Exception:
            ttl = -2

        retry_after = ttl if ttl and ttl > 0 else window_s
        log.warning(
            log_event,
            method=method,
            path=path,
            actor=actor,
            limit=limit,
            window_s=window_s,
            count=count,
            ttl=ttl,
            **(extra_fields or {}),
        )
        raise HTTPException(status_code=429, detail="rate_limited", headers={"Retry-After": str(retry_after)})

    return False, 0


async def _emit_privileged_rate_limit_alert(*, redis_client, method: str, path: str, actor: str, count: int, limit: int, ttl: int, retry_after: int) -> None:
    alert_key = f"rl:http:alert:{method}:{path}:{actor}"
    should_emit = await redis_client.set(alert_key, 1, ex=PRIVILEGED_ALERT_WINDOW_S, nx=True)
    if should_emit:
        log.warning(
            "security.privileged_http_rate_limit_alert",
            method=method,
            path=path,
            actor=actor,
            count=count,
            limit=limit,
            ttl=ttl,
            retry_after=retry_after,
            alert_window_s=PRIVILEGED_ALERT_WINDOW_S,
        )


async def minimal_route_rate_limit(request: Request) -> None:
    method = str(request.method or "GET").upper()
    route = request.scope.get("route")
    route_path = str(getattr(route, "path", "") or request.url.path or "/").rstrip("/") or "/"
    route_rules = _default_http_rate_limits(method, route_path)
    is_privileged = _is_privileged_route(route_path)
    client_ip = _extract_blockable_ip(request)

    actor = _extract_rate_limit_actor(request)
    route_key = f"rl:http:{method}:{route_path}:{actor}"

    try:
        r = get_redis()
        if client_ip:
            await _ensure_ip_not_blocked(r, ip=client_ip, method=method, path=route_path)
        try:
            await _enforce_rate_limit_rules(
                r,
                base_key=route_key,
                rules=route_rules,
                method=method,
                path=route_path,
                actor=actor,
                log_event="http.route_rate_limited",
            )
        except HTTPException:
            if is_privileged:
                limit, window_s = route_rules[-1]
                try:
                    ttl = int(await r.ttl(f"{route_key}:w{window_s}"))
                except Exception:
                    ttl = -2
                retry_after = ttl if ttl and ttl > 0 else window_s
                try:
                    await _emit_privileged_rate_limit_alert(
                        redis_client=r,
                        method=method,
                        path=route_path,
                        actor=actor,
                        count=limit + 1,
                        limit=limit,
                        ttl=ttl,
                        retry_after=retry_after,
                    )
                except Exception as exc:
                    log.warning(
                        "security.privileged_http_rate_limit_alert_failed",
                        method=method,
                        path=route_path,
                        actor=actor,
                        err=type(exc).__name__,
                    )
            if client_ip:
                await _register_ip_violation(
                    r,
                    ip=client_ip,
                    method=method,
                    path=route_path,
                    reason="route_rate_limit",
                )
            raise

        actor_bucket, actor_rules = _actor_http_rate_limit(method, route_path)
        actor_key = f"rl:http:actor:{actor_bucket}:{actor}"
        try:
            await _enforce_rate_limit_rules(
                r,
                base_key=actor_key,
                rules=actor_rules,
                method=method,
                path=route_path,
                actor=actor,
                log_event="http.actor_rate_limited",
                extra_fields={"actor_bucket": actor_bucket},
            )
        except HTTPException:
            if client_ip:
                await _register_ip_violation(
                    r,
                    ip=client_ip,
                    method=method,
                    path=route_path,
                    reason=f"actor_rate_limit:{actor_bucket}",
                )
            raise

    except HTTPException:
        raise

    except Exception as exc:
        log.warning(
            "http.route_rate_limit_failed",
            method=method,
            path=route_path,
            actor=actor,
            err=type(exc).__name__,
        )


def require_room_creator(room_id_param: str = "room_id"):
    def deco(fn):
        if not asyncio.iscoroutinefunction(fn):
            log.error("require_room_creator.not_async", function=getattr(fn, "__qualname__", getattr(fn, "__name__", "?")))
            raise TypeError("require_room_creator может оборачивать только async-функции")

        sig = inspect.signature(fn)
        need_inject = "ident" not in sig.parameters

        @functools.wraps(fn)
        async def wrap(*args, **kwargs):
            ident: Identity | None = kwargs.get("ident")
            if not ident:
                log.warning("require_room_creator.no_ident", function=getattr(fn, "__qualname__", getattr(fn, "__name__", "?")))
                raise HTTPException(status_code=401, detail="Unauthorized")

            bound = sig.bind_partial(*args, **kwargs)
            if room_id_param not in bound.arguments:
                log.error("require_room_creator.param_missing", param=room_id_param)
                raise HTTPException(status_code=500, detail="room_id_param_not_found")

            r = get_redis()
            rid = int(bound.arguments[room_id_param])
            redis_params = await r.hgetall(f"room:{rid}:params")
            if not redis_params:
                log.warning("require_room_creator.room_not_found", rid=rid)
                raise HTTPException(status_code=404, detail="room_not_found")

            if int(redis_params.get("creator") or 0) != int(ident["id"]):
                log.warning("require_room_creator.forbidden", rid=rid, uid=ident["id"])
                raise HTTPException(status_code=403, detail="forbidden")

            return await fn(*args, **kwargs)

        if need_inject:
            params = list(sig.parameters.values()) + [inspect.Parameter("ident", kind=inspect.Parameter.KEYWORD_ONLY, default=Depends(get_identity))]
            wrap.__signature__ = sig.replace(parameters=params)
        else:
            wrap.__signature__ = sig

        _mark_route_guard(wrap, "require_room_creator")
        return wrap

    return deco


def rate_limited(key: Union[str, Callable[..., str]], *, limit: int, window_s: int):
    def deco(fn: Callable[..., Any]) -> Callable[..., Awaitable[Any]]:
        if not asyncio.iscoroutinefunction(fn):
            raise TypeError("rate_limited может оборачивать только async-функции")

        sig = inspect.signature(fn)

        @functools.wraps(fn)
        async def wrap(*a, **kw):
            bound = sig.bind_partial(*a, **kw)
            ctx = bound.arguments
            k = key(**ctx) if callable(key) else str(key)

            r = get_redis()
            created = await r.set(k, 1, ex=window_s, nx=True)
            cnt = 1 if created else int(await r.incr(k))
            if cnt == 1 and not created:
                try:
                    await r.expire(k, window_s)
                except Exception as e:
                    log.warning("rate_limit.expire_failed", key=k, window_s=window_s, err=type(e).__name__)

            if cnt > limit:
                try:
                    ttl = int(await r.ttl(k))
                except Exception:
                    ttl = -2

                retry_after = ttl if ttl and ttl > 0 else window_s
                log.warning("rate_limited", key=k, limit=limit, window_s=window_s, count=cnt, ttl=ttl)
                raise HTTPException(status_code=429, detail="rate_limited", headers={"Retry-After": str(retry_after)})

            return await fn(*a, **kw)

        wrap.__signature__ = sig
        _mark_route_guard(wrap, "rate_limited")
        return wrap

    return deco


def rate_limited_sio(key: Union[str, KeyBuilder], *, limit: int, window_s: int, session_ns: Optional[str] = None, fail_open: bool = True) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        if not asyncio.iscoroutinefunction(fn):
            raise TypeError("rate_limited_sio может оборачивать только async-функции")

        @functools.wraps(fn)
        async def wrap(sid: str, *a, **kw):
            try:
                uid: Optional[int] = None
                rid: Optional[int] = None
                if session_ns:
                    try:
                        sess = await sio.get_session(sid, namespace=session_ns)
                        uid = int(sess.get("uid") or 0) or None
                        rid = int(sess.get("rid") or 0) or None
                    except Exception:
                        uid = rid = None

                r = get_redis()
                k = key(sid=sid, *a, **kw, uid=uid, rid=rid) if callable(key) else str(key)
                created = await r.set(k, 1, ex=window_s, nx=True)
                cnt = 1 if created else int(await r.incr(k))

                if cnt == 1 and not created:
                    try:
                        await r.expire(k, window_s)
                    except Exception as e:
                        log.warning("sio.rate_limit.expire_failed", key=k, window_s=window_s, err=type(e).__name__)

                if cnt > limit:
                    try:
                        ttl = int(await r.ttl(k))
                    except Exception:
                        ttl = -2
                    retry_after = ttl if ttl and ttl > 0 else window_s
                    log.warning("sio.rate_limited", key=k, limit=limit, window_s=window_s, count=cnt, ttl=ttl)
                    return {"ok": False, "error": "rate_limited", "status": 429, "retry_after": retry_after}

            except Exception as e:
                log.warning("sio.ratelimit.error", err=type(e).__name__)
                if not fail_open:
                    return {"ok": False, "error": "rate_limit_internal", "status": 500}

            return await fn(sid, *a, **kw)

        return wrap

    return deco
