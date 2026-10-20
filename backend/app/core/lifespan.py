from __future__ import annotations
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
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


async def setup_subscription_roulette_schema(conn: AsyncConnection) -> None:
    for statement in (
        "ALTER TABLE settings ADD COLUMN IF NOT EXISTS subscription_roulette_enabled boolean NOT NULL DEFAULT false, "
        "ADD COLUMN IF NOT EXISTS subscription_roulette_round bigint NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_roulette_days smallint",
        "DROP INDEX IF EXISTS uq_subscription_grants_roulette_user_id",
        "DROP INDEX IF EXISTS uq_subscription_grants_roulette_user_round",
        "ALTER TABLE subscription_grants DROP CONSTRAINT IF EXISTS ck_subscription_grants_subscription_roulette_round_required",
    ):
        await conn.execute(text(statement))
    for table, name, condition in (
        ("users", "subscription_roulette_days_range", "subscription_roulette_days IS NULL OR subscription_roulette_days BETWEEN 1 AND 30"),
        ("settings", "subscription_roulette_round_range", "subscription_roulette_round >= 0"),
    ):
        constraint = f"ck_{table}_{name}"
        exists = await conn.scalar(text(
            "SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = to_regclass(:table) AND conname = :name)"
        ), {"table": table, "name": constraint})
        if not exists:
            await conn.execute(text(f"ALTER TABLE {table} ADD CONSTRAINT {constraint} CHECK ({condition})"))


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
            await setup_subscription_roulette_schema(conn)

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
