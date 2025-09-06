from __future__ import annotations
from contextlib import asynccontextmanager
from sqlalchemy import text
from ..db import engine, Base
from .logging import configure_logging
from .clients import init_clients, close_clients, get_redis
from ..services.storage_minio import ensure_bucket

@asynccontextmanager
async def lifespan(app):
    configure_logging()
    init_clients()

    # Postgres ping + bootstrap таблиц если пусто
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
        await conn.run_sync(Base.metadata.create_all)

    # Redis ping
    r = get_redis()
    await r.ping()

    # MinIO bucket
    ensure_bucket()

    yield

    await close_clients()
    await engine.dispose()
