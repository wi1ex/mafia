from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends, Response, Request
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_session
from ..models.user import User
from ..core.security import verify_telegram_auth, decode_token
from ..services.sessions import new_login_session, issue_access_token, rotate_refresh, logout as logout_sess, REFRESH_COOKIE
from ..services.storage_minio import download_telegram_photo, put_avatar, presign_avatar
from ..core.logging import log_action
from ..settings import settings


router = APIRouter()

unauth = HTTPException(status_code=401, detail="unauthorized")
bad = HTTPException(status_code=400, detail="bad payload")

@router.post("/telegram")
async def telegram_auth(request: Request, resp: Response, db: AsyncSession = Depends(get_session)):
    b = await request.json()
    if not {"id", "auth_date", "hash"}.issubset(b):
        raise bad
    if not verify_telegram_auth(b):
        raise unauth

    uid = int(b["id"])
    username = b.get("username")
    photo_url = b.get("photo_url")
    user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()

    filename = None
    if photo_url:
        dl = await download_telegram_photo(str(photo_url))
        if dl:
            c, ext = dl
            try:
                filename = put_avatar(uid, c, ext)
            except Exception:
                filename = None
    if user:
        vals = {"last_login_at": func.now()}
        if username is not None:
            vals["username"] = username
        if filename is not None:
            vals["photo_url"] = filename
        await db.execute(update(User).where(User.id == uid).values(**vals))
        await db.commit()
        user = (await db.execute(select(User).where(User.id == uid))).scalar_one()
    else:
        user = User(id=uid, username=username, role="user", photo_url=filename)
        db.add(user)
        await db.flush()
        await log_action(db, user_id=user.id, username=user.username, action="user_registered", details={"user_id": user.id})
        await db.commit()

    sid = await new_login_session(resp, user_id=user.id, role=user.role)
    at = issue_access_token(user_id=user.id, role=user.role, sid=sid)
    return {
        "access_token": at,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "photo_url": presign_avatar(user.photo_url) if user.photo_url else None,
            "role": user.role
        }
    }


@router.post("/refresh")
async def refresh(request: Request, resp: Response, db: AsyncSession = Depends(get_session)):
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw: raise unauth
    try:
        p = decode_token(raw)
        uid = int(p.get("sub") or 0)
        sid = p.get("sid")
        if not uid or not sid:
            raise ValueError
    except Exception:
        raise unauth
    if not await rotate_refresh(resp, raw_refresh_jwt=raw):
        raise unauth
    row = (await db.execute(select(User.role, User.photo_url, User.username).where(User.id == uid))).first()
    role, filename, username = (row[0], row[1], row[2]) if row else ("user", None, None)
    at = issue_access_token(user_id=uid, role=role, sid=sid)
    return {
        "access_token": at,
        "token_type": "bearer",
        "user": {
            "id": uid,
            "username": username,
            "photo_url": presign_avatar(filename) if filename else None,
            "role": role
        }
    }


@router.post("/logout")
async def logout(request: Request, resp: Response):
    uid = None
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        try:
            uid = int(decode_token(raw).get("sub") or 0) or None
        except Exception:
            uid = None
    if not uid:
        auth = request.headers.get("authorization")
        if auth and auth.lower().startswith("bearer "):
            try:
                uid = int(decode_token(auth[7:].strip()).get("sub") or 0) or None
            except Exception:
                uid = None
    if uid:
        await logout_sess(resp, user_id=uid)
    else:
        resp.delete_cookie(REFRESH_COOKIE, path="/api", domain=settings.DOMAIN)
    return {"status": "ok"}
