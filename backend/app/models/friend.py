from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, Integer, String, DateTime, CheckConstraint, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db import Base


class FriendLink(Base):
    __tablename__ = "friend_links"
    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_friend_links_pair"),
        CheckConstraint("requester_id <> addressee_id", name="ck_friend_links_self"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requester_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    addressee_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FriendCloseness(Base):
    __tablename__ = "friend_closeness"
    __table_args__ = (
        UniqueConstraint("user_low", "user_high", name="uq_friend_closeness_pair"),
        CheckConstraint("user_low < user_high", name="ck_friend_closeness_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_low: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    user_high: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    games_together: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
