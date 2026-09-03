from __future__ import annotations
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, String, BigInteger, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from ..core.db import Base


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    room_owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    head_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(8), nullable=False, default="normal", server_default="normal")
    rating_mode_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    result: Mapped[str] = mapped_column(String(8), nullable=False)
    black_alive_at_finish: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    roles: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    seats: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    points: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    scoring_rules: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    mmr: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    actions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")


class GameScoringSettings(Base):
    __tablename__ = "game_scoring_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    rules: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
