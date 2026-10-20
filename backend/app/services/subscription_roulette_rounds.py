from __future__ import annotations
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.settings import AppSettings
from ..models.user import User


async def start_roulette_round(session: AsyncSession, settings: AppSettings) -> int:
    settings.subscription_roulette_round += 1
    result = await session.execute(
        update(User).values(
            subscription_roulette_days=None,
        ).execution_options(synchronize_session=False)
    )
    return int(result.rowcount or 0)
