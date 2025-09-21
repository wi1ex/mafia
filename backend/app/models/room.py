from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from ..db import Base


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    creator: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(64), nullable=False)
    user_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    visitor_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
