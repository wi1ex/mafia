from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING
from fastapi import HTTPException, status
from sqlalchemy import select, update
if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from ..models.settings import AppSettings
    from ..models.user import User


@dataclass(frozen=True)
class SiteRulesUpdate:
    version: int
    affected_users: int


async def _lock_site_rules_settings(session: AsyncSession) -> AppSettings:
    from ..models.settings import AppSettings
    from ..security.parameters import ensure_app_settings

    await ensure_app_settings(session)
    row = await session.scalar(
        select(AppSettings)
        .where(AppSettings.id == 1)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(status_code=503, detail="settings_unavailable")

    return row


async def update_site_rules_version(session: AsyncSession, *, actor_user_id: int, actor_username: str,) -> SiteRulesUpdate:
    from ..core.logging import log_action
    from ..models.user import User

    row = await _lock_site_rules_settings(session)
    version = int(row.rules_version or 0) + 1
    row.rules_version = version
    result = await session.execute(
        update(User)
        .where(User.deleted_at.is_(None), User.telegram_id.is_not(None))
        .values(rules_required_version=version)
        .execution_options(synchronize_session=False)
    )
    affected_users = int(result.rowcount or 0)
    await log_action(
        session,
        user_id=actor_user_id,
        username=actor_username,
        action="admin_site_rules_update",
        details=f"Обновление правил сайта: version={version} affected_users={affected_users}",
        commit=False,
    )
    await session.commit()
    return SiteRulesUpdate(version=version, affected_users=affected_users)


async def accept_site_rules_version(session: AsyncSession, *, user_id: int, version: int,) -> User:
    from ..core.logging import log_action
    from ..models.user import User

    await _lock_site_rules_settings(session)
    user = await session.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    if user.deleted_at:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_deleted")

    if version != int(user.rules_required_version or 0):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="rules_updated")

    if user.rules_acceptance_required:
        user.rules_accepted_version = version
        await log_action(
            session,
            user_id=user_id,
            username=user.username,
            action="site_rules_accepted",
            details=f"Пользователь принял изменения правил сайта: version={version}",
            commit=False,
        )
    await session.commit()
    return user
