from __future__ import annotations
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from ..core.db import Base


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    room_owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    result: Mapped[str] = mapped_column(String(8), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    roles: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    points: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    mmr: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    actions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
