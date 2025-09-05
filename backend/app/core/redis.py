from __future__ import annotations
import redis.asyncio as redis
from ..settings import settings

def build_redis() -> redis.Redis:
    if settings.REDIS_PASSWORD:
        return redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, password=settings.REDIS_PASSWORD, decode_responses=True)
    return redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)
