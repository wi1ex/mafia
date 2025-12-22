from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.db import get_session
from ...security.decorators import log_route, require_roles_deco
from ...security.parameters import ensure_app_settings, get_cached_settings, sync_cache_from_row
from ...schemas.admin import (
    AdminSettingsOut,
    SiteSettingsOut,
    SiteSettingsUpdateIn,
    GameSettingsOut,
    GameSettingsUpdateIn,
    PublicSettingsOut,
)

router = APIRouter()


def _site_out(row) -> SiteSettingsOut:
    return SiteSettingsOut(
        registration_enabled=bool(row.registration_enabled),
        rooms_can_create=bool(row.rooms_can_create),
        games_can_start=bool(row.games_can_start),
        rooms_limit_global=int(row.rooms_limit_global),
        rooms_limit_per_user=int(row.rooms_limit_per_user),
    )


def _game_out(row) -> GameSettingsOut:
    return GameSettingsOut(
        game_min_ready_players=int(row.game_min_ready_players),
        role_pick_seconds=int(row.role_pick_seconds),
        mafia_talk_seconds=int(row.mafia_talk_seconds),
        player_talk_seconds=int(row.player_talk_seconds),
        player_talk_short_seconds=int(row.player_talk_short_seconds),
        player_foul_seconds=int(row.player_foul_seconds),
        night_action_seconds=int(row.night_action_seconds),
        vote_seconds=int(row.vote_seconds),
    )


@log_route("admin.settings_public")
@router.get("/settings/public", response_model=PublicSettingsOut)
async def public_settings() -> PublicSettingsOut:
    settings = get_cached_settings()
    return PublicSettingsOut(
        registration_enabled=settings.registration_enabled,
        rooms_can_create=settings.rooms_can_create,
        games_can_start=settings.games_can_start,
    )


@log_route("admin.settings_get")
@require_roles_deco("admin")
@router.get("/settings", response_model=AdminSettingsOut)
async def get_settings(session: AsyncSession = Depends(get_session)) -> AdminSettingsOut:
    row = await ensure_app_settings(session)
    return AdminSettingsOut(site=_site_out(row), game=_game_out(row))


@log_route("admin.settings_site_update")
@require_roles_deco("admin")
@router.patch("/settings/site", response_model=SiteSettingsOut)
async def update_site_settings(payload: SiteSettingsUpdateIn, session: AsyncSession = Depends(get_session)) -> SiteSettingsOut:
    row = await ensure_app_settings(session)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)

    if data:
        await session.commit()
        await session.refresh(row)
    sync_cache_from_row(row)

    return _site_out(row)


@log_route("admin.settings_game_update")
@require_roles_deco("admin")
@router.patch("/settings/game", response_model=GameSettingsOut)
async def update_game_settings(payload: GameSettingsUpdateIn, session: AsyncSession = Depends(get_session)) -> GameSettingsOut:
    row = await ensure_app_settings(session)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)

    if data:
        await session.commit()
        await session.refresh(row)
    sync_cache_from_row(row)

    return _game_out(row)
