from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db import Base


class GlobalChatMessage(Base):
    __tablename__ = "global_chat_messages"
    __table_args__ = (
        UniqueConstraint("user_id", "client_message_id", name="uq_global_chat_messages_user_client_message_id"),
        Index("ix_global_chat_messages_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    client_message_id: Mapped[object] = mapped_column(UUID(as_uuid=True), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reply_to_message_id: Mapped[int | None] = mapped_column(ForeignKey("global_chat_messages.id", ondelete="SET NULL"), nullable=True, index=True)
    image_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)


class GlobalChatMessageReaction(Base):
    __tablename__ = "global_chat_message_reactions"
    __table_args__ = (
        Index("ix_global_chat_message_reactions_message_id", "message_id"),
    )

    message_id: Mapped[int] = mapped_column(ForeignKey("global_chat_messages.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    emoji: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
