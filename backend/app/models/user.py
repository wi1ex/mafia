from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, String, DateTime, Boolean, Text, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(20), nullable=False, index=True, unique=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    avatar_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    nickname_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    nickname_changes_left: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    profile_theme_color: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    profile_theme_icon: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, unique=True, index=True)
    telegram_nickname: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    password_temp: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    hotkeys_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    tg_invites_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    allow_friend_requests: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_visit_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
