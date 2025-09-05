from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Response, Request
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from ...db import get_session
from ...models.user import User
from ...schemas.auth import TelegramAuthIn, AuthOut, UserOut
from ...core.security import verify_telegram_auth, decode_token
from ...services.sessions import new_login_session, issue_access_token, rotate_refresh, logout as logout_sess, REFRESH_COOKIE
from ...services.storage_minio import download_telegram_photo, put_avatar
from ...services.logs import log_action
from ..deps import get_current_user

router = APIRouter()

@router.post("/telegram", response_model=AuthOut)
async def telegram_auth(payload: TelegramAuthIn, db: AsyncSession = Depends(get_session), resp: Response = None):
    data = payload.model_dump()
    if not verify_telegram_auth(data):
        raise HTTPException(status_code=401, detail="invalid telegram signature")

    res = await db.execute(select(User).where(User.id == payload.id))
    user = res.scalar_one_or_none()

    # скачать аватар в MinIO (не критично при ошибке)
    filename = None
    if payload.photo_url:
        dl = await download_telegram_photo(str(payload.photo_url))
        if dl:
            content, ext = dl
            try:
                filename = await put_avatar(payload.id, content, ext)
            except Exception:
                filename = None

    if user:
        # обновить username/аватар, last_login_at
        values = {"last_login_at": func.now()}
        if payload.username is not None:
            values["username"] = payload.username
        if filename is not None:
            values["photo_url"] = filename
        await db.execute(update(User).where(User.id == user.id).values(**values))
        await db.commit()
    else:
        user = User(
            id=payload.id,
            username=payload.username,
            role="user",
            photo_url=filename,
        )
        db.add(user)
        await db.flush()
        await log_action(db, user_id=user.id, user_nickname=user.username, action="user_registered", details={"user_id": user.id})
        await db.commit()

    sid = await new_login_session(resp, user_id=user.id, role=user.role)
    access = await issue_access_token(user_id=user.id, role=user.role, sid=sid)
    return AuthOut(access_token=access, user=UserOut(id=user.id, username=user.username, photo_url=user.photo_url, role=user.role))

@router.post("/refresh", response_model=AuthOut)
async def refresh(request: Request, resp: Response, db: AsyncSession = Depends(get_session)):
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status_code=401, detail="no refresh")
    # Декодируем СТАРЫЙ refresh для user_id и sid
    try:
        payload = decode_token(raw)
        user_id = int(payload.get("sub"))
        sid = payload.get("sid")
        if not user_id or not sid:
            raise ValueError("bad token")
    except Exception:
        raise HTTPException(status_code=401, detail="invalid refresh")

    # Ротация refresh-куки (валидность и single-session проверяются внутри)
    rotated = await rotate_refresh(resp, raw_refresh_jwt=raw)
    if not rotated:
        raise HTTPException(status_code=401, detail="invalid refresh")

    # Берём актуальную роль из БД и выпускаем access c тем же sid
    res = await db.execute(select(User.role).where(User.id == user_id))
    role = res.scalar_one_or_none() or "user"
    access = await issue_access_token(user_id=user_id, role=role, sid=sid)

    # Профиль фронту можно подтянуть отдельно через /users/me
    return AuthOut(access_token=access, user=UserOut(id=user_id, username=None, photo_url=None, role=role))

@router.post("/logout")
async def logout(resp: Response = None, current_user: User = Depends(get_current_user)):
    await logout_sess(resp, user_id=current_user.id)
    return {"status": "ok"}
