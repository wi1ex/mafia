from __future__ import annotations
import structlog
from sqlalchemy import text
from typing import AsyncIterator
from contextlib import asynccontextmanager
from ..security.parameters import ensure_app_settings
from ..services.game_scoring import ensure_game_scoring_settings
from ..security.admin_guard import assert_protected_admin_invariants, ensure_protected_admin
from ..models.sanction_rules import ensure_sanction_rules
from .background_tasks import LifespanBackgroundTasks, verify_runtime_dependencies
from .clients import close_clients, init_clients
from .db import Base, SessionLocal, engine
from .logging import configure_logging
from .settings import settings


@asynccontextmanager
async def lifespan(app) -> AsyncIterator[None]:
    configure_logging()
    log = structlog.get_logger()
    log.info("app.startup", project=settings.PROJECT_NAME, domain=settings.DOMAIN)
    init_clients()

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.execute(text("SELECT pg_advisory_xact_lock(20261020, 1)"))
            await conn.run_sync(Base.metadata.create_all)

            # BEGIN ONE-TIME DC MIGRATION
            from ..services.coin_prices import DEFAULT_DC_PACKAGES
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS dc_balance BIGINT NOT NULL DEFAULT 0"))
            await conn.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conrelid = 'users'::regclass
                          AND conname = 'ck_users_nonnegative_dc_balance'
                    ) THEN
                        ALTER TABLE users ADD CONSTRAINT ck_users_nonnegative_dc_balance
                            CHECK (dc_balance >= 0);
                    END IF;
                END $$;
            """))
            await conn.execute(text(f"ALTER TABLE settings ADD COLUMN IF NOT EXISTS dc_coin_packages TEXT NOT NULL DEFAULT '{DEFAULT_DC_PACKAGES}'"))
            await conn.execute(text("ALTER TABLE settings ADD COLUMN IF NOT EXISTS payments_enabled BOOLEAN NOT NULL DEFAULT TRUE"))
            await conn.execute(text("ALTER TABLE settings ALTER COLUMN dc_coin_packages SET NOT NULL"))
            await conn.execute(text("ALTER TABLE notifs ADD COLUMN IF NOT EXISTS event_key VARCHAR(192)"))
            await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_notifs_event_key ON notifs(event_key) WHERE event_key IS NOT NULL"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_subscription_purchases_actor_id ON subscription_purchases(actor_id)"))
            await conn.execute(text("ALTER TABLE settings DROP COLUMN IF EXISTS donation_url"))
            await conn.execute(text("DROP TABLE IF EXISTS kassa_payments"))
            # END ONE-TIME DC MIGRATION

        async with SessionLocal() as session:
            await ensure_app_settings(session)
            await ensure_game_scoring_settings(session)
            await ensure_sanction_rules(session)
            await ensure_protected_admin(session)
            await assert_protected_admin_invariants(session)

    except Exception:
        log.exception("app.startup.db_failed")
        raise

    try:
        await verify_runtime_dependencies()
    except Exception:
        log.exception("app.startup.deps_failed")
        raise

    background_tasks = LifespanBackgroundTasks(log)
    background_tasks.start()
    log.info("app.ready")

    try:
        yield
    finally:
        await background_tasks.stop()

        try:
            await close_clients()
        except Exception:
            log.warning("app.shutdown.close_clients_failed")

        try:
            await engine.dispose()
        except Exception:
            log.warning("app.shutdown.engine_dispose_failed")

        log.info("app.shutdown.ok")
