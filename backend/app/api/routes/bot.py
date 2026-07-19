from __future__ import annotations
from contextlib import suppress
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, exists, and_
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.db import get_session
from ...core.logging import log_action
from ...models.user import User
from ...schemas.common import Ok
from ...schemas.auth import BotVerifyIn, BotResetIn, TempPasswordOut, BotStatusIn, BotStatusOut
from ...security.decorators import rate_limited
from ...security.passwords import (
    hash_password_async,
    make_temp_password,
    password_needs_rehash,
    verify_password_async,
)
from ..utils import (
    normalize_username,
    require_bot_token,
    bot_verify_telegram_rate_key,
    bot_verify_account_rate_key,
    bot_reset_rate_key,
    bot_status_rate_key,
    find_user_by_username,
    fetch_active_sanctions,
    fetch_active_sanctions_by_telegram,
    pick_active_sanction_kind,
    emit_auth_profile_sync,
    force_logout_user,
)
from ...realtime.sio import sio
from ...services.global_chat import emit_global_chat_permissions_updated

router = APIRouter()


@router.post("/verify", response_model=Ok)
@rate_limited(bot_verify_telegram_rate_key, limit=5, window_s=300)
@rate_limited(bot_verify_account_rate_key, limit=5, window_s=300)
async def verify(payload: BotVerifyIn, db: AsyncSession = Depends(get_session), _: None = Depends(require_bot_token)) -> Ok:
    username = normalize_username(payload.username)
    if payload.telegram_id <= 0:
        raise HTTPException(status_code=422, detail="invalid_telegram_id")

    user = await find_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    if user.deleted_at:
        raise HTTPException(status_code=403, detail="user_deleted")

    if not user.password_hash:
        raise HTTPException(status_code=403, detail="password_not_set")

    if not await verify_password_async(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")

    if password_needs_rehash(user.password_hash):
        user.password_hash = await hash_password_async(payload.password)

    user_active = await fetch_active_sanctions(db, int(user.id))
    if pick_active_sanction_kind(user_active):
        raise HTTPException(status_code=403, detail="user_sanctioned")

    existing_tg = await db.scalar(select(exists().where(and_(User.telegram_id == int(payload.telegram_id), User.id != user.id))))
    if existing_tg:
        raise HTTPException(status_code=409, detail="telegram_in_use")

    if user.telegram_id and int(user.telegram_id) != int(payload.telegram_id):
        raise HTTPException(status_code=409, detail="telegram_already_linked")

    tg_active = await fetch_active_sanctions_by_telegram(db, int(payload.telegram_id))
    if pick_active_sanction_kind(tg_active):
        raise HTTPException(status_code=403, detail="telegram_sanctioned")

    user.telegram_id = int(payload.telegram_id)
    await db.commit()

    await log_action(
        db,
        user_id=int(user.id),
        username=user.username,
        action="telegram_verified",
        details=f"Привязка Telegram: user_id={int(user.id)} username={user.username} tg_id={int(payload.telegram_id)}",
    )

    with suppress(Exception):
        await sio.emit(
            "telegram_verified",
            {"user_id": int(user.id), "telegram_verified": True},
            room=f"user:{int(user.id)}",
            namespace="/auth",
        )
    with suppress(Exception):
        await emit_auth_profile_sync(int(user.id), role=str(user.role or "user"))
    with suppress(Exception):
        await emit_global_chat_permissions_updated(int(user.id))

    return Ok()


@router.post("/reset_password", response_model=TempPasswordOut)
@rate_limited(bot_reset_rate_key, limit=3, window_s=3600)
async def reset_password(payload: BotResetIn, db: AsyncSession = Depends(get_session), _: None = Depends(require_bot_token)) -> TempPasswordOut:
    if payload.telegram_id <= 0:
        raise HTTPException(status_code=422, detail="invalid_telegram_id")

    user = await db.scalar(select(User).where(User.telegram_id == int(payload.telegram_id)))
    if not user:
        raise HTTPException(status_code=403, detail="not_verified")

    if user.deleted_at:
        raise HTTPException(status_code=403, detail="user_deleted")

    temp_password = make_temp_password()
    user.password_hash = await hash_password_async(temp_password)
    user.password_temp = True
    await db.commit()
    await force_logout_user(int(user.id), reason="password_reset")

    await log_action(
        db,
        user_id=int(user.id),
        username=user.username,
        action="password_reset",
        details=f"Сброс пароля через бот: user_id={int(user.id)} username={user.username} tg_id={int(payload.telegram_id)}",
    )

    return TempPasswordOut(temp_password=temp_password, username=user.username)


@router.post("/status", response_model=BotStatusOut)
@rate_limited(bot_status_rate_key, limit=30, window_s=60)
async def status(payload: BotStatusIn, db: AsyncSession = Depends(get_session), _: None = Depends(require_bot_token)) -> BotStatusOut:
    if payload.telegram_id <= 0:
        raise HTTPException(status_code=422, detail="invalid_telegram_id")

    exists_row = await db.scalar(select(1).where(User.telegram_id == int(payload.telegram_id)).limit(1))
    return BotStatusOut(verified=bool(exists_row))
