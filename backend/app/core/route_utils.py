from __future__ import annotations
import asyncio
import functools
import structlog
from typing import Callable, Any
from fastapi import HTTPException
from ..services.sessions import get_current_user


def log_route(name: str):
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def wrap(*a, **kw):
                log = structlog.get_logger().bind(route=name)
                log.debug("route.start")
                try:
                    res = await fn(*a, **kw)
                    log.debug("route.end")
                    return res
                except Exception:
                    log.exception("route.error")
                    raise
            return wrap
        else:
            @functools.wraps(fn)
            def wrap_sync(*a, **kw):
                log = structlog.get_logger().bind(route=name)
                log.debug("route.start")
                try:
                    res = fn(*a, **kw)
                    log.debug("route.end")
                    return res
                except Exception:
                    log.exception("route.error")
                    raise
            return wrap_sync
    return deco


def require_roles(*roles: str):
    async def _dep():
        user = await get_current_user()
        if roles and getattr(user, "role", None) not in roles:
            raise HTTPException(status_code=403, detail="forbidden")
        return True
    return _dep
