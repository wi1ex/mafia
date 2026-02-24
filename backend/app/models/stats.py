from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db import Base


class UserGameStats(Base):
    __tablename__ = "stats"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    games_total_finished: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    games_decisive: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    games_won: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    games_hosted: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_fouls_received: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    don_checks_first_night: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    don_checks_first_night_found: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    misses_due_to_me: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    vote_leave_day12: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    farewell_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    farewell_correct: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    first_killed_best_move_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    best_move_black_0: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    best_move_black_1: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    best_move_black_2: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    best_move_black_3: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    current_win_streak: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    current_loss_streak: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    best_win_streak: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    best_loss_streak: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    citizen_games: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    citizen_wins: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    sheriff_games: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    sheriff_wins: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    mafia_games: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    mafia_wins: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    don_games: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    don_wins: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
