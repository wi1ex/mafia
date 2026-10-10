from __future__ import annotations
from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, Integer, JSON, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db import Base


class SanctionRulesConfig(Base):
    __tablename__ = "sanction_rules_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    sections: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


async def get_sanction_rules(session: AsyncSession) -> SanctionRulesConfig | None:
    return await session.get(SanctionRulesConfig, 1)
