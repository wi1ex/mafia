from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
from sqlalchemy import BigInteger, CheckConstraint, DateTime, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db import Base


class CoinPurchase(Base):
    __tablename__ = "coin_purchases"
    __table_args__ = (CheckConstraint("quantity >= 0", name="nonnegative_quantity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(BigInteger)
    request_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    invoice_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    provider_event_id: Mapped[str | None] = mapped_column(String(160), unique=True)
    offer_id: Mapped[str | None] = mapped_column(String(128))
    product_id: Mapped[str | None] = mapped_column(String(128))
    tracking_token: Mapped[str | None] = mapped_column(String(96), unique=True)
    email: Mapped[str | None] = mapped_column(String(254))
    payment_url: Mapped[str | None] = mapped_column(Text)
    balance_before: Mapped[int | None] = mapped_column(BigInteger)
    balance_after: Mapped[int | None] = mapped_column(BigInteger)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    provider_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    event_log: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
