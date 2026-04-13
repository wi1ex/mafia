from __future__ import annotations
import asyncio
import structlog
from datetime import datetime, timedelta
from sqlalchemy import text
from typing import AsyncIterator
from contextlib import asynccontextmanager, suppress
from ..core.db import Base, engine, SessionLocal
from ..core.settings import settings
from ..api.utils import (
    emit_expired_timed_sanctions_chat_notices,
    delete_stale_unverified_accounts,
    sync_expired_profile_subscriptions,
)
from ..security.admin_guard import assert_protected_admin_invariants
from ..security.parameters import ensure_app_settings, refresh_app_settings
from ..services.minio import ensure_bucket
from .clients import close_clients, get_redis, init_clients
from .logging import configure_logging


def _next_local_daily_run_at(*, hour: int, minute: int = 0) -> datetime:
    now = datetime.now().astimezone()
    next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    return next_run


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
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_theme_color VARCHAR(32)"))
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_theme_icon VARCHAR(32)"))

            # remove after the first deploy with profile theme defaults recovery.
            valid_theme_colors = (
                "violet",
                "mulberry",
                "garnet",
                "terracotta",
                "amber",
                "olive",
                "emerald",
                "lagoon",
                "azure",
                "midnight",
            )
            valid_theme_icons = ("none", *(f"sub_icon{idx}" for idx in range(1, 20)))
            valid_theme_colors_sql = ", ".join(f"'{value}'" for value in valid_theme_colors)
            valid_theme_icons_sql = ", ".join(f"'{value}'" for value in valid_theme_icons)
            theme_defaults_result = await conn.execute(text(f"""
                UPDATE users AS u
                SET
                    profile_theme_color = CASE
                        WHEN lower(trim(coalesce(u.profile_theme_color, ''))) IN ({valid_theme_colors_sql})
                            THEN lower(trim(u.profile_theme_color))
                        ELSE 'terracotta'
                    END,
                    profile_theme_icon = CASE
                        WHEN lower(trim(coalesce(u.profile_theme_icon, ''))) IN ({valid_theme_icons_sql})
                            THEN lower(trim(u.profile_theme_icon))
                        ELSE 'sub_icon1'
                    END
                WHERE EXISTS (
                    SELECT 1
                    FROM user_subscriptions AS us
                    WHERE us.user_id = u.id
                      AND us.starts_at <= CURRENT_TIMESTAMP
                      AND us.ends_at > CURRENT_TIMESTAMP
                )
                  AND (
                    lower(trim(coalesce(u.profile_theme_color, ''))) NOT IN ({valid_theme_colors_sql})
                    OR lower(trim(coalesce(u.profile_theme_icon, ''))) NOT IN ({valid_theme_icons_sql})
                  )
            """))
            if theme_defaults_result.rowcount and theme_defaults_result.rowcount > 0:
                log.info("app.subscriptions.theme_defaults_synced", users=int(theme_defaults_result.rowcount))
            # remove after the first deploy with profile theme defaults recovery.

        async with SessionLocal() as session:
            await ensure_app_settings(session)
            await assert_protected_admin_invariants(session)
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
    expired_subscriptions_task: asyncio.Task[None] | None = None
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

    async def expired_profile_subscriptions_loop() -> None:
        try:
            while True:
                next_run = _next_local_daily_run_at(hour=3, minute=0)
                delay_s = max(0.0, (next_run - datetime.now(next_run.tzinfo)).total_seconds())
                try:
                    log.info("app.subscriptions.expired_sync.scheduled", run_at=next_run.isoformat(), delay_s=int(delay_s))
                    await asyncio.sleep(delay_s)
                    synced = await sync_expired_profile_subscriptions()
                    log.info("app.subscriptions.expired_sync.done", synced=synced, scheduled_at=next_run.isoformat())
                except Exception:
                    log.exception("app.subscriptions.expired_sync.failed")
        except asyncio.CancelledError:
            pass

    settings_task = asyncio.create_task(settings_pubsub_loop())
    expired_sanctions_chat_task = asyncio.create_task(expired_sanctions_chat_loop())
    expired_subscriptions_task = asyncio.create_task(expired_profile_subscriptions_loop())
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
            if expired_subscriptions_task:
                expired_subscriptions_task.cancel()
                with suppress(asyncio.CancelledError):
                    await expired_subscriptions_task
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
