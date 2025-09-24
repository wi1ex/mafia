from __future__ import annotations
import structlog
from fastapi import HTTPException
from ..core.clients import get_redis

__all__ = [
    "rate_limit",
]

log = structlog.get_logger()


async def rate_limit(key: str, *, limit: int, window_s: int) -> None:
    r = get_redis()
    created = await r.set(key, 1, ex=window_s, nx=True)
    if created:
        cnt = 1
    else:
        cnt = int(await r.incr(key))
        if cnt == 1:
            try:
                await r.expire(key, window_s)
            except Exception:
                pass
    if cnt > limit:
        try:
            ttl = int(await r.ttl(key))
        except Exception:
            ttl = -2
        retry_after = ttl if ttl and ttl > 0 else window_s
        log.warning("rate_limited", key=key, limit=limit, window_s=window_s, count=cnt, ttl=ttl)
        raise HTTPException(status_code=429, detail="rate_limited", headers={"Retry-After": str(retry_after)})
