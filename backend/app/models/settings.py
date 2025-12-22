from __future__ import annotations
from sqlalchemy import Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db import Base
from ..core.settings import settings


class AppSettings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    registration_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    rooms_can_create: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    games_can_start: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    rooms_limit_global: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    rooms_limit_per_user: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    game_min_ready_players: Mapped[int] = mapped_column(Integer, nullable=False, server_default=str(settings.GAME_MIN_READY_PLAYERS))
    role_pick_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default=str(settings.ROLE_PICK_SECONDS))
    mafia_talk_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default=str(settings.MAFIA_TALK_SECONDS))
    player_talk_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default=str(settings.PLAYER_TALK_SECONDS))
    player_talk_short_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default=str(settings.PLAYER_TALK_SHORT_SECONDS))
    player_foul_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default=str(settings.PLAYER_FOUL_SECONDS))
    night_action_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default=str(settings.NIGHT_ACTION_SECONDS))
    vote_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default=str(settings.VOTE_SECONDS))
