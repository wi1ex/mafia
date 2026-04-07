from __future__ import annotations
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.settings import settings
from ..models.user import User
from ..services.user_cache import write_user_profile_cache

log = structlog.get_logger()


def get_protected_admin_user_id() -> int:
    try:
        uid = int(getattr(settings, "PROTECTED_ADMIN_USER_ID", 0) or 0)
    except Exception:
        uid = 0
    return uid if uid > 0 else 0


def is_protected_admin_uid(user_id: int | str | None) -> bool:
    try:
        uid = int(user_id or 0)
    except Exception:
        return False

    protected_uid = get_protected_admin_user_id()
    return 0 < protected_uid == uid


def normalize_protected_admin_role(user_id: int | str | None, role: str | None, *, fallback_role: str | None = "user") -> str:
    normalized_role = str(role or "").strip().lower()
    normalized_fallback = str(fallback_role or "user").strip().lower() or "user"

    if normalized_role != "admin":
        return normalized_role or normalized_fallback

    if is_protected_admin_uid(user_id):
        return "admin"

    return normalized_fallback if normalized_fallback != "admin" else "user"


async def assert_protected_admin_invariants(session: AsyncSession) -> None:
    protected_uid = get_protected_admin_user_id()
    if protected_uid <= 0:
        raise RuntimeError("PROTECTED_ADMIN_USER_ID must be a positive integer")

    protected_user = await session.get(User, protected_uid)
    if protected_user is None:
        raise RuntimeError(f"Protected admin user {protected_uid} does not exist")

    if getattr(protected_user, "deleted_at", None) is not None:
        raise RuntimeError(f"Protected admin user {protected_uid} is deleted")

    protected_role = str(getattr(protected_user, "role", "") or "").strip().lower()
    if protected_role != "admin":
        raise RuntimeError(f"Protected admin user {protected_uid} must have role=admin")

    rows = await session.execute(select(User.id).where(User.role == "admin"))
    admin_ids = sorted({int(row[0]) for row in rows.all() if row and row[0] is not None})
    if protected_uid not in admin_ids:
        raise RuntimeError(f"Protected admin user {protected_uid} is missing from admin set")

    unexpected_admin_ids = [uid for uid in admin_ids if uid != protected_uid]
    if unexpected_admin_ids:
        raise RuntimeError(
            f"Unexpected admin users found: {unexpected_admin_ids}; only {protected_uid} is allowed to have role=admin"
        )

    await write_user_profile_cache(
        protected_uid,
        username=str(protected_user.username),
        role="admin",
        avatar_name=protected_user.avatar_name,
    )

    log.info("security.protected_admin.audit_ok", protected_admin_user_id=protected_uid)
