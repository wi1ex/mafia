from __future__ import annotations
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncEngine
from .logging import configure_logging
from ..db import engine
from ..db import Base
import redis.asyncio as redis
from ..core.redis import build_redis

@asynccontextmanager
async def lifespan(app):
    configure_logging()
    # проверка Redis
    r: redis.Redis = build_redis()
    await r.ping()
    # авто-создание таблиц при старте
    eng: AsyncEngine = engine
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await eng.dispose()
    await r.close()
