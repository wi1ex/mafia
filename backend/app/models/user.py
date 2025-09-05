from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base

class User(Base):
    __tablename__ = "users"

    # PK = Telegram ID (BigInt), по требованию
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # tg username (не уникален глобально), хранится для справки
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    # уникальный ник внутри платформы
    nickname: Mapped[Optional[str]] = mapped_column(String(32), unique=True, nullable=True, index=True)
    # отображаемое имя
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # роль
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    # аватар
    photo_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # активность
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
