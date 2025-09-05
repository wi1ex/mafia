from __future__ import annotations
import asyncio
from alembic import context
from sqlalchemy.engine import Connection
from app.db import Base, engine, DATABASE_URL

# Alembic Config (ini). Логирование через fileConfig не используем, чтобы не требовать секций [formatters]/[handlers].
config = context.config

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Offline режим — генерирует SQL без подключения."""
    url = DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    """Онлайн режим — через sync-обёртку для async-движка."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    async with engine.connect() as conn:
        await conn.run_sync(do_run_migrations)

def main() -> None:
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        asyncio.run(run_migrations_online())

main()
