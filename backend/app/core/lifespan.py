from __future__ import annotations
import asyncio
import time
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

    t0 = time.perf_counter()
    init_clients()
    log.info("clients.init.ok")

    r = get_redis()
    redis_ping = asyncio.create_task(r.ping())
    minio_ready = asyncio.to_thread(ensure_bucket)

    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
        await conn.run_sync(Base.metadata.create_all)
        log.info("db.migrations.applied")

    await asyncio.gather(redis_ping, minio_ready)
    log.info("deps.ready", dur_ms=round((time.perf_counter() - t0) * 1000, 2))

    try:
        yield
    finally:
        t1 = time.perf_counter()
        await close_clients()
        await engine.dispose()
        log.info("app.stopped", dur_ms=round((time.perf_counter() - t1) * 1000, 2))
