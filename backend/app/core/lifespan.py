from __future__ import annotations
import structlog
from sqlalchemy import text
from typing import AsyncIterator
from contextlib import asynccontextmanager
from ..security.parameters import ensure_app_settings
from ..models.sanction_rules import ensure_sanction_rules
from ..services.game_scoring import ensure_game_scoring_settings
from ..security.admin_guard import assert_protected_admin_invariants
##############################################################
from ..scripts.import_manual_subscription_grants import import_manual_grants
##############################################################
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
            await conn.run_sync(Base.metadata.create_all)
            ##############################################################
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS rating_host_minutes BIGINT NOT NULL DEFAULT 0"))
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS rating_host_reward_days BIGINT NOT NULL DEFAULT 0"))
            await conn.execute(text("ALTER TABLE games ADD COLUMN IF NOT EXISTS host_reward_minutes INTEGER"))
            await conn.execute(text("ALTER TABLE subscription_grants ADD COLUMN IF NOT EXISTS source_log_id INTEGER"))
            await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_subscription_grants_source_log_id ON subscription_grants (source_log_id)"))
            await conn.execute(text("""
                INSERT INTO subscription_grants (user_id, issued_at, reason, months, days, payment_id)
                SELECT user_id, processed_at, 'Оплата', subscription_months, 0, id
                FROM kassa_payments
                WHERE status = 'processed' AND processed_at IS NOT NULL
                    AND user_id IS NOT NULL AND subscription_months > 0
                ON CONFLICT (payment_id) DO NOTHING
            """))
            ##############################################################

        async with SessionLocal() as session:
            ##############################################################
            imported_grants = await import_manual_grants(session)
            await session.commit()
            log.info("subscription.manual_history.imported", **imported_grants)
            ##############################################################
            await ensure_app_settings(session)
            await ensure_game_scoring_settings(session)
            await ensure_sanction_rules(session)
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
