from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from ..core.db import Base


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    creator: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    creator_name: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(32), nullable=False)
    user_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    privacy: Mapped[str] = mapped_column(String(8), nullable=False, server_default="open")
    game: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    visitors: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    screen_time: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
