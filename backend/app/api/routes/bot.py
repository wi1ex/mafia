from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, exists, func, literal, and_
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.db import get_session
from ...core.logging import log_action
from ...models.user import User
from ...schemas.common import Ok
from ...schemas.auth import BotVerifyIn, BotResetIn, TempPasswordOut, BotStatusIn, BotStatusOut
from ...security.passwords import verify_password, hash_password, make_temp_password
from ..utils import normalize_username, require_bot_token

router = APIRouter()


@router.post("/verify", response_model=Ok)
async def verify(payload: BotVerifyIn, db: AsyncSession = Depends(get_session), _: None = Depends(require_bot_token)) -> Ok:
    username = normalize_username(payload.username)
    if payload.telegram_id <= 0:
        raise HTTPException(status_code=422, detail="invalid_telegram_id")

    stmt = select(User).where(User.username.ilike(username))
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    if user.deleted_at:
        raise HTTPException(status_code=403, detail="user_deleted")

    if not user.password_hash:
        raise HTTPException(status_code=403, detail="password_not_set")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")

    existing_tg = await db.scalar(select(exists().where(and_(User.telegram_id == int(payload.telegram_id), User.id != user.id))))
    if existing_tg:
        raise HTTPException(status_code=409, detail="telegram_in_use")

    if user.telegram_id and int(user.telegram_id) != int(payload.telegram_id):
        raise HTTPException(status_code=409, detail="telegram_already_linked")

    user.telegram_id = int(payload.telegram_id)
    await db.commit()

    await log_action(
        db,
        user_id=int(user.id),
        username=user.username,
        action="telegram_verified",
        details=f"Привязка Telegram: user_id={int(user.id)} tg_id={int(payload.telegram_id)}",
    )

    return Ok()


@router.post("/reset_password", response_model=TempPasswordOut)
async def reset_password(payload: BotResetIn, db: AsyncSession = Depends(get_session), _: None = Depends(require_bot_token)) -> TempPasswordOut:
    username = normalize_username(payload.username)
    if payload.telegram_id <= 0:
        raise HTTPException(status_code=422, detail="invalid_telegram_id")

    stmt = select(User).where(User.username.ilike(username))
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    if user.deleted_at:
        raise HTTPException(status_code=403, detail="user_deleted")

    if not user.telegram_id:
        raise HTTPException(status_code=403, detail="not_verified")

    if int(user.telegram_id) != int(payload.telegram_id):
        raise HTTPException(status_code=403, detail="telegram_mismatch")

    temp_password = make_temp_password()
    user.password_hash = hash_password(temp_password)
    user.password_temp = True
    await db.commit()

    await log_action(
        db,
        user_id=int(user.id),
        username=user.username,
        action="password_reset",
        details=f"Сброс пароля через бот: user_id={int(user.id)} tg_id={int(payload.telegram_id)}",
    )

    return TempPasswordOut(temp_password=temp_password)


@router.post("/status", response_model=BotStatusOut)
async def status(payload: BotStatusIn, db: AsyncSession = Depends(get_session), _: None = Depends(require_bot_token)) -> BotStatusOut:
    if payload.telegram_id <= 0:
        raise HTTPException(status_code=422, detail="invalid_telegram_id")

    exists_row = await db.scalar(select(1).where(User.telegram_id == int(payload.telegram_id)).limit(1))
    return BotStatusOut(verified=bool(exists_row))
