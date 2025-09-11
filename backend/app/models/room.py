from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    user_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user_durations: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
