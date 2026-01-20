from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db import Base


class UserSanction(Base):
    __tablename__ = "user_sanctions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    reason: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    issued_by_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    issued_by_name: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    revoked_by_name: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    expired_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
