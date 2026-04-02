from __future__ import annotations
import asyncio
import structlog
from sqlalchemy import text
from typing import AsyncIterator
from contextlib import asynccontextmanager, suppress
from ..core.db import Base, engine, SessionLocal
from ..core.settings import settings
from ..api.utils import emit_expired_timed_sanctions_chat_notices, delete_stale_unverified_accounts
from ..security.parameters import ensure_app_settings, refresh_app_settings
from ..services.minio import ensure_bucket
from .clients import close_clients, get_redis, init_clients
from .logging import configure_logging


@asynccontextmanager
async def lifespan(app) -> AsyncIterator[None]:
    configure_logging()
    log = structlog.get_logger()
    log.info("app.startup", project=settings.PROJECT_NAME, domain=settings.DOMAIN)

    init_clients()

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                text(
                    """
                    ALTER TABLE global_chat_messages
                    ADD COLUMN IF NOT EXISTS mention_spans JSONB NOT NULL DEFAULT '[]'::jsonb
                    """
                )
            )
        async with SessionLocal() as session:
            await ensure_app_settings(session)
    except Exception:
        log.exception("app.startup.db_failed")
        raise

    async def redis_ping():
        await get_redis().ping()

    async def minio_ready():
        await asyncio.to_thread(ensure_bucket)

    try:
        await asyncio.gather(redis_ping(), minio_ready())
    except Exception:
        log.exception("app.startup.deps_failed")
        raise

    settings_task: asyncio.Task[None] | None = None
    expired_sanctions_chat_task: asyncio.Task[None] | None = None
    stale_unverified_accounts_task: asyncio.Task[None] | None = None

    async def settings_pubsub_loop() -> None:
        r = get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe("settings:update")
        try:
            async for message in pubsub.listen():
                if not message or message.get("type") != "message":
                    continue
                try:
                    async with SessionLocal() as session:
                        await refresh_app_settings(session)
                except Exception:
                    log.warning("app.settings.refresh_failed")
        except asyncio.CancelledError:
            pass
        finally:
            with suppress(Exception):
                await pubsub.unsubscribe("settings:update")
            with suppress(Exception):
                await pubsub.close()

    async def expired_sanctions_chat_loop() -> None:
        try:
            while True:
                try:
                    await emit_expired_timed_sanctions_chat_notices()
                except Exception:
                    log.exception("app.sanctions.expired_chat_loop_failed")
                await asyncio.sleep(15)
        except asyncio.CancelledError:
            pass

    async def stale_unverified_accounts_loop() -> None:
        try:
            while True:
                try:
                    deleted = await delete_stale_unverified_accounts()
                    if deleted > 0:
                        log.info("app.users.auto_delete_unverified.done", deleted=deleted)
                except Exception:
                    log.exception("app.users.auto_delete_unverified.failed")
                await asyncio.sleep(15 * 60)
        except asyncio.CancelledError:
            pass

    settings_task = asyncio.create_task(settings_pubsub_loop())
    expired_sanctions_chat_task = asyncio.create_task(expired_sanctions_chat_loop())
    stale_unverified_accounts_task = asyncio.create_task(stale_unverified_accounts_loop())
    log.info("app.ready")

    try:
        yield
    finally:
        try:
            if settings_task:
                settings_task.cancel()
                with suppress(asyncio.CancelledError):
                    await settings_task
            if expired_sanctions_chat_task:
                expired_sanctions_chat_task.cancel()
                with suppress(asyncio.CancelledError):
                    await expired_sanctions_chat_task
            if stale_unverified_accounts_task:
                stale_unverified_accounts_task.cancel()
                with suppress(asyncio.CancelledError):
                    await stale_unverified_accounts_task
        except Exception:
            log.warning("app.shutdown.settings_task_failed")
        try:
            await close_clients()
        except Exception:
            log.warning("app.shutdown.close_clients_failed")
        try:
            await engine.dispose()
        except Exception:
            log.warning("app.shutdown.engine_dispose_failed")
        log.info("app.shutdown.ok")
