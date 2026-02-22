from __future__ import annotations
from contextlib import suppress
from typing import cast
from sqlalchemy import select, update, exists, func, literal, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Response
from ..utils import (
    broadcast_creator_rooms,
    SANCTION_TIMEOUT,
    SANCTION_BAN,
    SANCTION_SUSPEND,
    fetch_active_sanctions,
    fetch_sanctions_for_users,
    ensure_profile_changes_allowed,
    set_user_deleted,
    force_logout_user,
    normalize_username,
    is_protected_admin,
)
from ...models.user import User
from ...core.db import get_session
from ...core.settings import settings
from ...core.logging import log_action
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route, rate_limited
from ...services.text_moderation import enforce_clean_text
from ...schemas.common import Identity, Ok
from ...schemas.user import (
    UserOut,
    UsernameUpdateIn,
    AvatarUploadOut,
    UsernameUpdateOut,
    UserSanctionsOut,
    UserSanctionOut,
    UserUiPrefsIn,
    UserUiPrefsOut,
    PasswordChangeIn,
)
from ...security.passwords import hash_password, verify_password
from ...services.minio import put_avatar_async, delete_avatars_async, ALLOWED_CT, MAX_BYTES
from ...services.user_cache import write_user_profile_cache, invalidate_avatar_presign_cache

router = APIRouter()


@log_route("users.profile_info")
@rate_limited(lambda ident, **_: f"rl:profile_info:{ident['id']}", limit=10, window_s=1)
@router.get("/profile_info", response_model=UserOut)
async def profile_info(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserOut:
    user = await db.get(User, int(ident["id"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    uid = cast(int, user.id)
    await write_user_profile_cache(uid, username=str(user.username), role=str(user.role), avatar_name=user.avatar_name)
    active = await fetch_active_sanctions(db, uid)
    timeout = active.get(SANCTION_TIMEOUT)
    ban = active.get(SANCTION_BAN)
    suspend = active.get(SANCTION_SUSPEND)

    return UserOut(
        id=uid,
        username=user.username,
        avatar_name=user.avatar_name,
        role=user.role,
        telegram_verified=bool(user.telegram_id),
        password_temp=bool(user.password_temp),
        protected_user=is_protected_admin(uid),
        hotkeys_visible=bool(user.hotkeys_visible),
        tg_invites_enabled=bool(user.tg_invites_enabled),
        timeout_until=timeout.expires_at if timeout else None,
        suspend_until=suspend.expires_at if suspend else None,
        ban_active=bool(ban),
    )


@log_route("users.sanctions_history")
@rate_limited(lambda ident, **_: f"rl:sanctions_history:{ident['id']}", limit=10, window_s=1)
@router.get("/sanctions", response_model=UserSanctionsOut)
async def sanctions_history(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserSanctionsOut:
    user = await db.get(User, int(ident["id"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    uid = cast(int, user.id)
    sanctions_map = await fetch_sanctions_for_users(db, [uid])
    rows = sanctions_map.get(uid, [])
    items = [
        UserSanctionOut(
            id=cast(int, row.id),
            kind=str(row.kind),
            reason=row.reason or None,
            issued_at=row.issued_at,
            issued_by_id=cast(int, row.issued_by_id) if row.issued_by_id is not None else None,
            issued_by_name=row.issued_by_name,
            duration_seconds=row.duration_seconds,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
            revoked_by_id=cast(int, row.revoked_by_id) if row.revoked_by_id is not None else None,
            revoked_by_name=row.revoked_by_name,
        )
        for row in rows
    ]

    return UserSanctionsOut(items=items)


@log_route("users.update_username")
@rate_limited(lambda ident, **_: f"rl:update_username:{ident['id']}", limit=1, window_s=1)
@router.patch("/username", response_model=UsernameUpdateOut)
async def update_username(payload: UsernameUpdateIn, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UsernameUpdateOut:
    uid = int(ident["id"])
    new = normalize_username(payload.username)
    if new.lower().startswith(("deleted_", "user_")):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_username_format")

    enforce_clean_text(field="username", label="Никнейм", value=new)

    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if is_protected_admin(getattr(user, "id", 0)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="protected_user")

    await ensure_profile_changes_allowed(db, uid)

    if user.username == new:
        return UsernameUpdateOut(username=user.username)

    exists_case_ins = await db.scalar(select(exists().where(and_(func.lower(User.username) == func.lower(literal(new)), User.id != uid))))
    if exists_case_ins:
        raise HTTPException(status_code=409, detail="username_taken")

    old_username = user.username
    await db.execute(update(User).where(User.id == uid).values(username=new))
    await db.commit()
    await write_user_profile_cache(uid, username=new, role=str(user.role), avatar_name=user.avatar_name)

    await log_action(
        db,
        user_id=uid,
        username=new,
        action="username_updated",
        details=f"Изменение никнейма: {old_username} -> {new}",
    )

    await broadcast_creator_rooms(uid, update_name=new)
    return UsernameUpdateOut(username=new)


@log_route("users.update_ui_prefs")
@rate_limited(lambda ident, **_: f"rl:update_ui_prefs:{ident['id']}", limit=10, window_s=1)
@router.patch("/ui_prefs", response_model=UserUiPrefsOut)
async def update_ui_prefs(payload: UserUiPrefsIn, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserUiPrefsOut:
    uid = int(ident["id"])
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    old_hotkeys_visible = bool(user.hotkeys_visible)
    old_tg_invites_enabled = bool(user.tg_invites_enabled)

    if payload.hotkeys_visible is not None:
        user.hotkeys_visible = bool(payload.hotkeys_visible)
    if payload.tg_invites_enabled is not None:
        user.tg_invites_enabled = bool(payload.tg_invites_enabled)

    new_hotkeys_visible = bool(user.hotkeys_visible)
    new_tg_invites_enabled = bool(user.tg_invites_enabled)
    await db.commit()

    changes: list[str] = []
    if old_hotkeys_visible != new_hotkeys_visible:
        changes.append(f"hotkeys_visible: {int(old_hotkeys_visible)} -> {int(new_hotkeys_visible)}")
    if old_tg_invites_enabled != new_tg_invites_enabled:
        changes.append(f"tg_invites_enabled: {int(old_tg_invites_enabled)} -> {int(new_tg_invites_enabled)}")

    if changes:
        await log_action(
            db,
            user_id=uid,
            username=ident["username"],
            action="ui_prefs_updated",
            details="UI prefs updated: " + "; ".join(changes),
        )

    return UserUiPrefsOut(
        hotkeys_visible=new_hotkeys_visible,
        tg_invites_enabled=new_tg_invites_enabled,
    )


@log_route("users.change_password")
@rate_limited(lambda ident, **_: f"rl:change_password:{ident['id']}", limit=1, window_s=1)
@router.patch("/password", response_model=Ok)
async def change_password(payload: PasswordChangeIn, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    if user.deleted_at:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_deleted")

    if user.password_hash is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="password_not_set")

    password_hash = str(user.password_hash)
    if not verify_password(payload.current_password, password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

    user.password_hash = hash_password(payload.new_password)
    user.password_temp = False
    await db.commit()

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="password_changed",
        details=f"Смена пароля user_id={uid} username={ident['username']}",
    )

    return Ok()


@log_route("users.unverify_telegram")
@rate_limited(lambda ident, **_: f"rl:unverify_telegram:{ident['id']}", limit=1, window_s=1)
@router.post("/unverify", response_model=Ok)
async def unverify_telegram(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    if user.deleted_at:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_deleted")

    prev_tg = user.telegram_id
    if prev_tg is None:
        return Ok()

    user.telegram_id = None
    await db.commit()

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="telegram_unverified_self",
        details=f"Пользователь отвязал Telegram: user_id={uid} username={ident['username']} tg_id={prev_tg}",
    )

    return Ok()


@log_route("users.upload_avatar")
@rate_limited(lambda ident, **_: f"rl:upload_avatar:{ident['id']}", limit=1, window_s=1)
@router.post("/avatar", response_model=AvatarUploadOut)
async def upload_avatar(file: UploadFile = File(...), ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> AvatarUploadOut:
    uid = int(ident["id"])
    await ensure_profile_changes_allowed(db, uid)

    row = await db.execute(select(User.username, User.avatar_name, User.role).where(User.id == uid))
    rec = row.first()
    if not rec:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    db_username = str(rec[0])
    old_avatar_name = cast(str | None, rec[1])
    db_role = str(rec[2])
    ct = (file.content_type or "").split(";")[0].strip().lower()
    if ct not in ALLOWED_CT:
        raise HTTPException(status_code=415, detail="unsupported_media_type")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="empty_file")

    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="file_too_large")

    name = await put_avatar_async(uid, data, ct)
    if not name:
        raise HTTPException(status_code=422, detail="bad_image")

    await db.execute(update(User).where(User.id == uid).values(avatar_name=name))
    await db.commit()
    await write_user_profile_cache(uid, username=db_username, role=db_role, avatar_name=name)
    await invalidate_avatar_presign_cache(old_avatar_name)

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="avatar_updated",
        details="Изменение аватара",
    )

    await broadcast_creator_rooms(uid, avatar="set", avatar_name=name)
    return AvatarUploadOut(avatar_name=name)


@log_route("users.delete_avatar")
@rate_limited(lambda ident, **_: f"rl:delete_avatar:{ident['id']}", limit=1, window_s=1)
@router.delete("/avatar", response_model=Ok)
async def delete_avatar(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    await ensure_profile_changes_allowed(db, uid)

    row = await db.execute(select(User.username, User.avatar_name, User.role).where(User.id == uid))
    rec = row.first()
    if not rec:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    db_username = str(rec[0])
    old_avatar_name = cast(str | None, rec[1])
    db_role = str(rec[2])

    await db.execute(update(User).where(User.id == uid).values(avatar_name=None))
    await db.commit()
    await write_user_profile_cache(uid, username=db_username, role=db_role, avatar_name=None)
    await invalidate_avatar_presign_cache(old_avatar_name)

    with suppress(Exception):
        await delete_avatars_async(uid)

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="avatar_deleted",
        details="Удаление аватара",
    )

    await broadcast_creator_rooms(uid, avatar="delete")
    return Ok()


@log_route("users.delete_account")
@rate_limited(lambda ident, **_: f"rl:delete_account:{ident['id']}", limit=1, window_s=5)
@router.delete("/account", response_model=Ok)
async def delete_account(resp: Response, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    if is_protected_admin(getattr(user, "id", 0)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="protected_user")

    await set_user_deleted(db, uid, deleted=True)

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="account_deleted",
        details=f"Удаление аккаунта user_id={uid} username={ident['username']}",
    )

    await force_logout_user(uid)
    resp.delete_cookie("rt", path="/api", domain=settings.DOMAIN, samesite="strict", secure=True)
    return Ok()
