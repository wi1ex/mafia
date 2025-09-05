from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData
from .settings import settings

DATABASE_URL = (
    f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)

engine = create_async_engine(
    DATABASE_URL,
    future=True,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# naming convention для корректных миграций Alembic
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
