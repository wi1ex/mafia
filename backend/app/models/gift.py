from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db import Base

GIFT_PRICES = (10, 25, 50, 100)


class Gift(Base):
    __tablename__ = "gifts"
    __table_args__ = (
        CheckConstraint(f"price_dc IN {GIFT_PRICES}", name="allowed_price"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    price_dc: Mapped[int] = mapped_column(Integer, nullable=False)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    avif_key: Mapped[str] = mapped_column(String(256), nullable=False)
    preview_key: Mapped[str] = mapped_column(String(256), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class UserGift(Base):
    __tablename__ = "user_gifts"
    __table_args__ = (
        CheckConstraint("dc_cost > 0", name="positive_cost"),
        Index("ix_user_gifts_gift_owner", "gift_id", "owner_id"),
        Index("ix_user_gifts_owner_acquired", "owner_id", "acquired_at", "id"),
        Index("ix_user_gifts_payer_acquired", "payer_id", "acquired_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gift_id: Mapped[int] = mapped_column(ForeignKey("gifts.id"), nullable=False)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    payer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    payer_username: Mapped[str] = mapped_column(String(20), nullable=False)
    owner_username: Mapped[str] = mapped_column(String(20), nullable=False)
    anonymous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    dc_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refund_recipient_id: Mapped[int | None] = mapped_column(BigInteger)
    balance_before: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
