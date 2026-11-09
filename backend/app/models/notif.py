from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, Integer, DateTime, ForeignKey, Text, func, String
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db import Base


class Notif(Base):
    __tablename__ = "notifs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    event_key: Mapped[str | None] = mapped_column(String(192), nullable=True, unique=True)
    title: Mapped[str] = mapped_column(String(64), nullable=False, server_default="Уведомление")
    text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotifInboxState(Base):
    __tablename__ = "notif_inbox_state"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    cleared_through_id: Mapped[int] = mapped_column(Integer, nullable=False)
