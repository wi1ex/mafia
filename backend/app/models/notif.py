from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, Integer, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db import Base


class Notif(Base):
    __tablename__ = "notifs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
