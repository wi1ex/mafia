from __future__ import annotations
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.sanction_rules import SanctionRulesConfig, default_sanction_rules


async def ensure_sanction_rules(session: AsyncSession) -> SanctionRulesConfig:
    row = await session.get(SanctionRulesConfig, 1)
    if row is not None:
        return row

    row = SanctionRulesConfig(id=1, sections=default_sanction_rules())
    session.add(row)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        row = await session.get(SanctionRulesConfig, 1)
        if row is None:
            raise
    else:
        await session.refresh(row)

    return row
