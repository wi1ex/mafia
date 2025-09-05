from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager

from sqlalchemy import text
from starlette.types import ASGIApp
from ..db import engine
from .redis import build_redis


@asynccontextmanager
async def lifespan(app: ASGIApp):
    # Проверка Postgres
    async with engine.connect() as conn:
        await conn.execute(text("select 1"))
    # Проверка Redis
    r = build_redis()
    await r.ping()
    try:
        yield
    finally:
        await r.close()
        await engine.dispose()
