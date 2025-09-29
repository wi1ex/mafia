from __future__ import annotations
import asyncio
import functools
import inspect
from typing import Any, Callable, Awaitable, Union
import structlog
from fastapi import HTTPException, Depends
from ..schemas import Identity
from ..core.security import get_identity
from ..core.clients import get_redis

log = structlog.get_logger()


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
