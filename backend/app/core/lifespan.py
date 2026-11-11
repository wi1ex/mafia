from __future__ import annotations
import structlog
from sqlalchemy import text
from typing import AsyncIterator
from contextlib import asynccontextmanager
from ..security.parameters import ensure_app_settings
from ..services.game_scoring import ensure_game_scoring_settings
from ..security.admin_guard import assert_protected_admin_invariants, ensure_protected_admin
from ..models.sanction_rules import ensure_sanction_rules
# 111111111111111111111111111111111111111111111111111111111
from ..models.gift import GIFT_PRICES
from ..services.nomination_rewards import DEFAULT_NOMINATION_LEVELS_JSON
# 222222222222222222222222222222222222222222222222222222222
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

            # 111111111111111111111111111111111111111111111111111111111
            await conn.execute(text("ALTER TABLE user_gifts ADD COLUMN IF NOT EXISTS display_order INTEGER"))
            if await conn.scalar(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'gifts'::regclass AND conname = 'ck_gifts_allowed_price'
                )
            """)):
                await conn.execute(text("ALTER TABLE gifts DROP CONSTRAINT ck_gifts_allowed_price"))
                await conn.execute(text(f"""
                    ALTER TABLE gifts ADD CONSTRAINT ck_gifts_allowed_catalog_price
                    CHECK (price_dc IN {GIFT_PRICES})
                """))
            await conn.execute(text(f"""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS nomination_rewarded_levels JSONB
                NOT NULL DEFAULT '{DEFAULT_NOMINATION_LEVELS_JSON}'
            """))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS show_last_activity BOOLEAN NOT NULL DEFAULT TRUE"
            ))
            # 222222222222222222222222222222222222222222222222222222222

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
    # 111111111111111111111111111111111111111111111111111111111
    background_tasks.start(backfill_nomination_rewards=True)
    # background_tasks.start()
    # 222222222222222222222222222222222222222222222222222222222
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
