from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..core.db import Base


class ContactRequestRecord(Base):
    __tablename__ = "contact_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    contact: Mapped[str] = mapped_column(String(160), nullable=False)
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    replies: Mapped[list["ContactRequestReply"]] = relationship(lazy="selectin", order_by="ContactRequestReply.id", cascade="all, delete-orphan",)


class ContactRequestReply(Base):
    __tablename__ = "contact_request_replies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_request_id: Mapped[int] = mapped_column(ForeignKey("contact_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    author_username: Mapped[str] = mapped_column(String(20), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
