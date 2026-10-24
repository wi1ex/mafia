from __future__ import annotations
import structlog
from sqlalchemy import text
from typing import AsyncIterator
from contextlib import asynccontextmanager
from ..security.parameters import ensure_app_settings
from ..services.game_scoring import ensure_game_scoring_settings
from ..security.admin_guard import assert_protected_admin_invariants
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

            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_roulette_days smallint "
                "CONSTRAINT ck_users_subscription_roulette_days_range CHECK (subscription_roulette_days BETWEEN 1 AND 30)"
            ))
            await conn.execute(text(
                "ALTER TABLE settings ADD COLUMN IF NOT EXISTS subscription_roulette_state bigint NOT NULL DEFAULT 0"
            ))
            await conn.execute(text(
                "ALTER TABLE settings ADD COLUMN IF NOT EXISTS streams_fullscreen_enabled boolean NOT NULL DEFAULT false"
            ))
            await conn.execute(text(
                "ALTER TABLE settings DROP COLUMN IF EXISTS streams_can_start"
            ))

        async with SessionLocal() as session:
            await ensure_app_settings(session)
            await ensure_game_scoring_settings(session)
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
