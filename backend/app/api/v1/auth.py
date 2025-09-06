from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Response, Request
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from ...db import get_session
from ...models.user import User
from ...core.security import verify_telegram_auth, decode_token
from ...services.sessions import new_login_session, issue_access_token, rotate_refresh, logout as logout_sess, REFRESH_COOKIE
from ...services.storage_minio import download_telegram_photo, put_avatar, presign_avatar
from ...services.logs import log_action
from ...settings import settings

router = APIRouter()

@router.post("/telegram")
async def telegram_auth(request: Request, db: AsyncSession = Depends(get_session), resp: Response = None):
    body = await request.json()
    required = {"id", "auth_date", "hash"}
    if not required.issubset(body.keys()):
        raise HTTPException(status_code=400, detail="bad payload")
    if not verify_telegram_auth(body):
        raise HTTPException(status_code=401, detail="invalid telegram signature")

    uid = int(body["id"])
    username = body.get("username")
    photo_url_raw = body.get("photo_url")

    res = await db.execute(select(User).where(User.id == uid))
    user = res.scalar_one_or_none()

    filename = None
    if photo_url_raw:
        dl = await download_telegram_photo(str(photo_url_raw))
        if dl:
            content, ext = dl
            try:
                filename = put_avatar(uid, content, ext)
            except Exception:
                filename = None

    if user:
        values = {"last_login_at": func.now()}
        if username is not None:
            values["username"] = username
        if filename is not None:
            values["photo_url"] = filename
        await db.execute(update(User).where(User.id == uid).values(**values))
        await db.commit()
        user = (await db.execute(select(User).where(User.id == uid))).scalar_one()
    else:
        user = User(id=uid, username=username, role="user", photo_url=filename)
        db.add(user)
        await db.flush()
        await log_action(db, user_id=user.id, username=user.username, action="user_registered", details={"user_id": user.id})
        await db.commit()

    sid = await new_login_session(resp, user_id=user.id, role=user.role)
    access = issue_access_token(user_id=user.id, role=user.role, sid=sid)
    return {
        "access_token": access,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "photo_url": presign_avatar(user.photo_url) if user.photo_url else None,
            "role": user.role,
        },
    }

@router.post("/refresh")
async def refresh(request: Request, resp: Response, db: AsyncSession = Depends(get_session)):
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status_code=401, detail="no refresh")
    # получить user_id/sid из старого refresh
    try:
        payload = decode_token(raw)
        user_id = int(payload.get("sub"))
        sid = payload.get("sid")
        if not user_id or not sid:
            raise ValueError("bad token")
    except Exception:
        raise HTTPException(status_code=401, detail="invalid refresh")

    rotated = await rotate_refresh(resp, raw_refresh_jwt=raw)
    if not rotated:
        raise HTTPException(status_code=401, detail="invalid refresh")

    # роль и актуальный filename из БД
    res = await db.execute(select(User.role, User.photo_url, User.username).where(User.id == user_id))
    row = res.first()
    role = row[0] if row else "user"
    filename = row[1] if row else None
    username = row[2] if row else None

    access = issue_access_token(user_id=user_id, role=role, sid=sid)
    return {
        "access_token": access,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "username": username,
            "photo_url": presign_avatar(filename) if filename else None,
            "role": role,
        },
    }

@router.post("/logout")
async def logout(request: Request, resp: Response):
    user_id = None
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        try:
            payload = decode_token(raw)
            user_id = int(payload.get("sub") or 0) or None
        except Exception:
            pass
    if not user_id:
        auth = request.headers.get("authorization")
        if auth and auth.lower().startswith("bearer "):
            try:
                payload = decode_token(auth[7:].strip())
                user_id = int(payload.get("sub") or 0) or None
            except Exception:
                pass
    if user_id:
        await logout_sess(resp, user_id=user_id)
    else:
        resp.delete_cookie(REFRESH_COOKIE, path="/api", domain=settings.DOMAIN)
    return {"status": "ok"}
