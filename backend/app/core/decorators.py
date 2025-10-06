from __future__ import annotations
import asyncio
import functools
import inspect
from typing import Any, Callable, Awaitable, Union, Optional
import structlog
from fastapi import HTTPException, Depends
from ..core.clients import get_redis
from ..core.security import get_identity
from ..realtime.sio import sio
from ..schemas import Identity

log = structlog.get_logger()

KeyBuilder = Callable[..., str]


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

                except Exception:
                    lg.exception("route.error")
                    raise
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

                except Exception:
                    lg.exception("route.error")
                    raise
            return wrap_sync

    return deco


def require_roles(*roles: str):
    async def _dep(ident: Identity = Depends(get_identity)) -> bool:
        if roles and ident["role"] not in roles:
            raise HTTPException(status_code=403, detail="forbidden")
        return True

    return _dep


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
                except Exception:
                    pass

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

                k = key(sid=sid, *a, **kw, uid=uid, rid=rid) if callable(key) else str(key)

                r = get_redis()
                created = await r.set(k, 1, ex=window_s, nx=True)
                cnt = 1 if created else int(await r.incr(k))

                if cnt == 1 and not created:
                    try:
                        await r.expire(k, window_s)
                    except Exception:
                        pass

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
