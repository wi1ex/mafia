from __future__ import annotations
from datetime import date, datetime
from sqlalchemy import BigInteger, Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db import Base


class SiteUpdate(Base):
    __tablename__ = "updates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    update_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UpdateRead(Base):
    __tablename__ = "update_reads"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    update_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
