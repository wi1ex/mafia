from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db import Base


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_subscriptions_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SubscriptionGrant(Base):
    __tablename__ = "subscription_grants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    months: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    days: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    payment_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    source_log_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
