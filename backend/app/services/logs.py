from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.log import AppLog

async def log_action(db: AsyncSession, *, user_id: int | None, user_nickname: str | None, action: str, details: dict):
    db.add(AppLog(user_id=user_id, user_nickname=user_nickname, action=action, details=details))
    await db.flush()
