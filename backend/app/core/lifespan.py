from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator
from sqlalchemy import text
from ..db import Base, engine
from .clients import close_clients, get_redis, init_clients
from .logging import configure_logging
from ..services.storage_minio import ensure_bucket


@asynccontextmanager
async def lifespan(app) -> AsyncIterator[None]:
    configure_logging()
    init_clients()

    r = get_redis()
    redis_ping = asyncio.create_task(r.ping())
    minio_ready = asyncio.to_thread(ensure_bucket)

    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
        await conn.run_sync(Base.metadata.create_all)

    await asyncio.gather(redis_ping, minio_ready)

    try:
        yield
    finally:
        await close_clients()
        await engine.dispose()
