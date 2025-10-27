from __future__ import annotations
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from ..core.settings import settings

engine = create_async_engine(
    settings.pg_dsn,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=20,
    max_overflow=20,
    pool_timeout=10,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

_metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    metadata = _metadata


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
