from __future__ import annotations
from datetime import datetime
from typing import Any
from sqlalchemy import BigInteger, DateTime, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db import Base


class SubscriptionPurchase(Base):
    __tablename__ = "subscription_purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    days: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    months: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    dc_cost: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    request_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    balance_before: Mapped[int | None] = mapped_column(BigInteger)
    balance_after: Mapped[int | None] = mapped_column(BigInteger)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
