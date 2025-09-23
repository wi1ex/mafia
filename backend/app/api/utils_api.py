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
    async with r.pipeline(transaction=True) as pipe:
        await pipe.incr(key, 1)
        await pipe.expire(key, window_s)
        cnt, _ = await pipe.execute()
    if int(cnt) > limit:
        log.warning("rate_limited", key=key, limit=limit, window_s=window_s, count=int(cnt))
        raise HTTPException(status_code=429, detail="rate_limited", headers={"Retry-After": str(window_s)})
