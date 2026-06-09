from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db import Base


class LavaPayment(Base):
    __tablename__ = "lava_payments"
    __table_args__ = (
        UniqueConstraint("contract_id", name="uq_lava_payments_contract_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    parent_contract_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    metadata_token: Mapped[Optional[str]] = mapped_column(String(96), nullable=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="created")
    event_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    product_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    product_title: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    offer_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    offer_title: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    plan: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    subscription_months: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payment_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
