from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator
import structlog
from sqlalchemy import text
from ..db import Base, engine
from .clients import close_clients, get_redis, init_clients
from .logging import configure_logging
from ..services.storage_minio import ensure_bucket
from ..settings import settings


@asynccontextmanager
async def lifespan(app) -> AsyncIterator[None]:
    configure_logging()
    log = structlog.get_logger()
    log.info("app.start", project=settings.PROJECT_NAME, domain=settings.DOMAIN)

    log.info("clients.init.start")
    init_clients()

    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
        await conn.run_sync(Base.metadata.create_all)

    async def redis_ping():
        await get_redis().ping()

    async def minio_ready():
        await asyncio.to_thread(ensure_bucket)

    await asyncio.gather(redis_ping(), minio_ready())
    log.info("clients.init.ok")
    try:
        yield
    finally:
        log.info("app.stop")
        await close_clients()
        await engine.dispose()
