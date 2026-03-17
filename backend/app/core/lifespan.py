from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager, suppress
from typing import AsyncIterator
import structlog
from sqlalchemy import text
from ..core.db import Base, engine, SessionLocal
from .clients import close_clients, get_redis, init_clients
from .logging import configure_logging
from ..services.minio import ensure_bucket
from ..security.parameters import ensure_app_settings, refresh_app_settings
from ..core.settings import settings

LEGACY_DELETED_SANCTION_TELEGRAM_ID = 830057336


async def _ensure_schema_compat(conn, log) -> None:
    await conn.execute(text("ALTER TABLE IF EXISTS user_sanctions ADD COLUMN IF NOT EXISTS telegram_id_snapshot BIGINT"))
    await conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_user_sanctions_telegram_id_snapshot "
            "ON user_sanctions (telegram_id_snapshot)"
        )
    )
    await conn.execute(
        text(
            "UPDATE user_sanctions AS s "
            "SET telegram_id_snapshot = u.telegram_id "
            "FROM users AS u "
            "WHERE s.user_id = u.id "
            "AND s.telegram_id_snapshot IS NULL "
            "AND u.telegram_id IS NOT NULL"
        )
    )
    # One legacy deleted account had sanctions before telegram snapshots existed.
    rows = await conn.execute(
        text(
            "SELECT DISTINCT s.user_id "
            "FROM user_sanctions AS s "
            "JOIN users AS u ON u.id = s.user_id "
            "WHERE s.telegram_id_snapshot IS NULL "
            "AND u.deleted_at IS NOT NULL"
        )
    )
    orphan_user_ids = [int(row[0]) for row in rows.all() if row and row[0] is not None]
    if len(orphan_user_ids) == 1:
        legacy_user_id = orphan_user_ids[0]
        await conn.execute(
            text(
                "UPDATE user_sanctions "
                "SET telegram_id_snapshot = :telegram_id "
                "WHERE user_id = :user_id "
                "AND telegram_id_snapshot IS NULL"
            ),
            {"telegram_id": LEGACY_DELETED_SANCTION_TELEGRAM_ID, "user_id": legacy_user_id},
        )
        log.info(
            "app.startup.legacy_deleted_sanction_backfilled",
            user_id=legacy_user_id,
            telegram_id=LEGACY_DELETED_SANCTION_TELEGRAM_ID,
        )
    elif len(orphan_user_ids) > 1:
        log.warning(
            "app.startup.legacy_deleted_sanction_backfill_skipped",
            orphan_users=orphan_user_ids,
        )


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
            await _ensure_schema_compat(conn, log)
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

    settings_task = asyncio.create_task(settings_pubsub_loop())

    log.info("app.ready")

    try:
        yield
    finally:
        try:
            if settings_task:
                settings_task.cancel()
                with suppress(asyncio.CancelledError):
                    await settings_task
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
