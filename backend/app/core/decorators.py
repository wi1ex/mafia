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
from ..schemas.common import Identity

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


def require_roles_deco(*roles: str):
    def deco(fn):
        if not asyncio.iscoroutinefunction(fn):
            raise TypeError("require_roles_deco может оборачивать только async-функции")

        sig = inspect.signature(fn)
        need_inject = "ident" not in sig.parameters

        @functools.wraps(fn)
        async def wrap(*args, **kwargs):
            ident: Identity | None = kwargs.get("ident")
            if not ident:
                log.warning("require_roles.missing_identity")
                raise HTTPException(status_code=401, detail="Unauthorized")

            if roles and ident["role"] not in roles:
                log.warning("require_roles.forbidden", role=ident["role"], need=roles)
                raise HTTPException(status_code=403, detail="forbidden")

            return await fn(*args, **kwargs)

        if need_inject:
            params = list(sig.parameters.values()) + [inspect.Parameter("ident", kind=inspect.Parameter.KEYWORD_ONLY, default=Depends(get_identity))]
            wrap.__signature__ = sig.replace(parameters=params)
        else:
            wrap.__signature__ = sig

        return wrap

    return deco


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

                r = get_redis()
                k = key(sid=sid, *a, **kw, uid=uid, rid=rid) if callable(key) else str(key)
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
