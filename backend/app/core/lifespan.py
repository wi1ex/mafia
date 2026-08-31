from __future__ import annotations
import structlog
from contextlib import asynccontextmanager
from typing import AsyncIterator
from sqlalchemy import text
from ..security.admin_guard import assert_protected_admin_invariants
from ..security.parameters import ensure_app_settings
from ..services.game_scoring import ensure_game_scoring_settings
from ..services.sanction_rules import ensure_sanction_rules
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


            # The project uses create_all rather than a migration runner.  Keep the
            # existing games table compatible with the new persisted mode snapshot.
            await conn.execute(
                text(
                    "ALTER TABLE games "
                    "ADD COLUMN IF NOT EXISTS mode VARCHAR(8) NOT NULL DEFAULT 'normal'"
                )
            )
            # Games recorded before this feature have no reliable mode snapshot and
            # must never participate in rating calculations.
            await conn.execute(text("UPDATE games SET mode = 'normal' WHERE mode IS NULL"))
            await conn.execute(
                text(
                    "ALTER TABLE games "
                    "ADD COLUMN IF NOT EXISTS scoring_rules JSONB NOT NULL DEFAULT '{}'::jsonb"
                )
            )


        async with SessionLocal() as session:
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
