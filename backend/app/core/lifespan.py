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
    emit_auth_profile_sync,
    fetch_online_user_ids,
    notify_expiring_profile_subscriptions,
    sync_expired_profile_subscriptions,
)
from ..security.admin_guard import assert_protected_admin_invariants
from ..security.parameters import ensure_app_settings, refresh_app_settings
from ..services.minio import ensure_bucket
from ..realtime.utils import recalculate_all_friend_closeness
from .clients import close_clients, get_redis, init_clients
from .logging import configure_logging
from ..services.nickname_limits import (
    FREE_NICKNAME_CHANGE_LIMIT,
    SUBSCRIPTION_NICKNAME_CHANGE_LIMIT,
    reset_monthly_nickname_change_limits,
)


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
            # AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
            await conn.execute(text(
                "ALTER TABLE friend_closeness "
                "ADD COLUMN IF NOT EXISTS room_seconds_together INTEGER NOT NULL DEFAULT 0"
            ))
            await conn.execute(text(
                "ALTER TABLE user_sanctions "
                "ADD COLUMN IF NOT EXISTS description VARCHAR(2048)"
            ))
            await conn.execute(text(
                "ALTER TABLE users "
                "ADD COLUMN IF NOT EXISTS nickname_changes_left INTEGER"
            ))
            await conn.execute(text(
                "UPDATE users u "
                "SET nickname_changes_left = CASE "
                "WHEN EXISTS ("
                "SELECT 1 FROM user_subscriptions s "
                "WHERE s.user_id = u.id AND s.starts_at <= NOW() AND s.ends_at > NOW()"
                f") THEN {SUBSCRIPTION_NICKNAME_CHANGE_LIMIT} ELSE {FREE_NICKNAME_CHANGE_LIMIT} END "
                "WHERE u.nickname_changes_left IS NULL"
            ))
            await conn.execute(text(
                "UPDATE users "
                f"SET nickname_changes_left = LEAST(GREATEST(nickname_changes_left, 0), {SUBSCRIPTION_NICKNAME_CHANGE_LIMIT}) "
                f"WHERE nickname_changes_left < 0 OR nickname_changes_left > {SUBSCRIPTION_NICKNAME_CHANGE_LIMIT}"
            ))
            await conn.execute(text(
                "ALTER TABLE users "
                "ALTER COLUMN nickname_changes_left SET DEFAULT 1"
            ))
            await conn.execute(text(
                "ALTER TABLE users "
                "ALTER COLUMN nickname_changes_left SET NOT NULL"
            ))
            await conn.execute(text(
                "CREATE TABLE IF NOT EXISTS contact_requests ("
                "id SERIAL PRIMARY KEY, "
                "user_id BIGINT, "
                "contact VARCHAR(160) NOT NULL, "
                "topic VARCHAR(120) NOT NULL, "
                "text TEXT NOT NULL, "
                "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
                ")"
            ))
            await conn.execute(text("DROP TABLE IF EXISTS update_reads"))
            await conn.execute(text("DROP TABLE IF EXISTS updates"))
            # AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA

        async with SessionLocal() as session:
            await ensure_app_settings(session)
            await assert_protected_admin_invariants(session)

        # AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
        async with SessionLocal() as session:
            await recalculate_all_friend_closeness(session)
            await session.commit()
            log.info("app.friends.closeness_rebuild.done")
        # AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA

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
        async def sync_online_profiles_after_nickname_limit_reset() -> int:
            try:
                online_user_ids = await fetch_online_user_ids(get_redis())
            except Exception:
                log.warning("app.users.nickname_changes_monthly_reset.online_lookup_failed")
                return 0

            synced = 0
            for uid in online_user_ids:
                with suppress(Exception):
                    await emit_auth_profile_sync(uid)
                    synced += 1
            return synced

        try:
            while True:
                next_run = _next_local_daily_run_at(hour=3, minute=0)
                delay_s = max(0.0, (next_run - datetime.now(next_run.tzinfo)).total_seconds())
                log.info(
                    "app.subscriptions.maintenance.scheduled",
                    run_at=next_run.isoformat(),
                    delay_s=int(delay_s),
                )
                await asyncio.sleep(delay_s)
                try:
                    reset_users = await reset_monthly_nickname_change_limits()
                    if reset_users > 0:
                        synced_online_profiles = await sync_online_profiles_after_nickname_limit_reset()
                        log.info(
                            "app.users.nickname_changes_monthly_reset.done",
                            reset_users=reset_users,
                            synced_online_profiles=synced_online_profiles,
                            scheduled_at=next_run.isoformat(),
                        )
                except Exception:
                    log.exception("app.users.nickname_changes_monthly_reset.failed")
                try:
                    synced = await sync_expired_profile_subscriptions()
                    log.info(
                        "app.subscriptions.expired_sync.done",
                        synced=synced,
                        scheduled_at=next_run.isoformat(),
                    )
                except Exception:
                    log.exception("app.subscriptions.expired_sync.failed")
                try:
                    notified = await notify_expiring_profile_subscriptions()
                    log.info(
                        "app.subscriptions.expiring_soon.done",
                        notified=notified,
                        scheduled_at=next_run.isoformat(),
                    )
                except Exception:
                    log.exception("app.subscriptions.expiring_soon.failed")
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
