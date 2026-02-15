from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.settings import settings as core_settings
from ..models.settings import AppSettings


@dataclass(frozen=True)
class AppSettingsSnapshot:
    registration_enabled: bool
    rooms_can_create: bool
    rooms_can_enter: bool
    games_can_start: bool
    streams_can_start: bool
    verification_restrictions: bool
    rooms_limit_global: int
    rooms_limit_per_user: int
    rooms_empty_ttl_seconds: int
    rooms_single_ttl_minutes: int
    season_start_game_number: int
    game_min_ready_players: int
    role_pick_seconds: int
    mafia_talk_seconds: int
    player_talk_seconds: int
    player_talk_short_seconds: int
    player_foul_seconds: int
    night_action_seconds: int
    vote_seconds: int
    winks_limit: int
    knocks_limit: int
    wink_spot_chance_percent: int


_CACHE: Optional[AppSettingsSnapshot] = None


def _defaults() -> AppSettingsSnapshot:
    return AppSettingsSnapshot(
        registration_enabled=True,
        rooms_can_create=True,
        rooms_can_enter=True,
        games_can_start=True,
        streams_can_start=True,
        verification_restrictions=True,
        rooms_limit_global=100,
        rooms_limit_per_user=3,
        rooms_empty_ttl_seconds=core_settings.ROOMS_EMPTY_TTL_SECONDS,
        rooms_single_ttl_minutes=core_settings.ROOMS_SINGLE_TTL_MINUTES,
        season_start_game_number=core_settings.SEASON_START_GAME_NUMBER,
        game_min_ready_players=core_settings.GAME_MIN_READY_PLAYERS,
        role_pick_seconds=core_settings.ROLE_PICK_SECONDS,
        mafia_talk_seconds=core_settings.MAFIA_TALK_SECONDS,
        player_talk_seconds=core_settings.PLAYER_TALK_SECONDS,
        player_talk_short_seconds=core_settings.PLAYER_TALK_SHORT_SECONDS,
        player_foul_seconds=core_settings.PLAYER_FOUL_SECONDS,
        night_action_seconds=core_settings.NIGHT_ACTION_SECONDS,
        vote_seconds=core_settings.VOTE_SECONDS,
        winks_limit=core_settings.WINKS_LIMIT,
        knocks_limit=core_settings.KNOCKS_LIMIT,
        wink_spot_chance_percent=core_settings.WINK_SPOT_CHANCE_PERCENT,
    )


def _snapshot_from_row(row: AppSettings) -> AppSettingsSnapshot:
    return AppSettingsSnapshot(
        registration_enabled=bool(row.registration_enabled),
        rooms_can_create=bool(row.rooms_can_create),
        rooms_can_enter=bool(row.rooms_can_enter),
        games_can_start=bool(row.games_can_start),
        streams_can_start=bool(row.streams_can_start),
        verification_restrictions=bool(row.verification_restrictions),
        rooms_limit_global=int(row.rooms_limit_global),
        rooms_limit_per_user=int(row.rooms_limit_per_user),
        rooms_empty_ttl_seconds=int(row.rooms_empty_ttl_seconds),
        rooms_single_ttl_minutes=int(row.rooms_single_ttl_minutes),
        season_start_game_number=int(row.season_start_game_number),
        game_min_ready_players=int(row.game_min_ready_players),
        role_pick_seconds=int(row.role_pick_seconds),
        mafia_talk_seconds=int(row.mafia_talk_seconds),
        player_talk_seconds=int(row.player_talk_seconds),
        player_talk_short_seconds=int(row.player_talk_short_seconds),
        player_foul_seconds=int(row.player_foul_seconds),
        night_action_seconds=int(row.night_action_seconds),
        vote_seconds=int(row.vote_seconds),
        winks_limit=int(row.winks_limit),
        knocks_limit=int(row.knocks_limit),
        wink_spot_chance_percent=int(row.wink_spot_chance_percent),
    )


def get_cached_settings() -> AppSettingsSnapshot:
    return _CACHE or _defaults()


def set_cached_settings(snapshot: AppSettingsSnapshot) -> None:
    global _CACHE
    _CACHE = snapshot


async def ensure_app_settings(session: AsyncSession) -> AppSettings:
    row = await session.scalar(select(AppSettings).limit(1))
    if not row:
        defaults = _defaults()
        row = AppSettings(
            id=1,
            registration_enabled=defaults.registration_enabled,
            rooms_can_create=defaults.rooms_can_create,
            rooms_can_enter=defaults.rooms_can_enter,
            games_can_start=defaults.games_can_start,
            streams_can_start=defaults.streams_can_start,
            verification_restrictions=defaults.verification_restrictions,
            rooms_limit_global=defaults.rooms_limit_global,
            rooms_limit_per_user=defaults.rooms_limit_per_user,
            rooms_empty_ttl_seconds=defaults.rooms_empty_ttl_seconds,
            rooms_single_ttl_minutes=defaults.rooms_single_ttl_minutes,
            season_start_game_number=defaults.season_start_game_number,
            game_min_ready_players=defaults.game_min_ready_players,
            role_pick_seconds=defaults.role_pick_seconds,
            mafia_talk_seconds=defaults.mafia_talk_seconds,
            player_talk_seconds=defaults.player_talk_seconds,
            player_talk_short_seconds=defaults.player_talk_short_seconds,
            player_foul_seconds=defaults.player_foul_seconds,
            night_action_seconds=defaults.night_action_seconds,
            vote_seconds=defaults.vote_seconds,
            winks_limit=defaults.winks_limit,
            knocks_limit=defaults.knocks_limit,
            wink_spot_chance_percent=defaults.wink_spot_chance_percent,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)

    set_cached_settings(_snapshot_from_row(row))
    return row


async def refresh_app_settings(session: AsyncSession) -> AppSettingsSnapshot:
    row = await ensure_app_settings(session)
    snapshot = _snapshot_from_row(row)
    set_cached_settings(snapshot)
    return snapshot


def sync_cache_from_row(row: AppSettings) -> AppSettingsSnapshot:
    snapshot = _snapshot_from_row(row)
    set_cached_settings(snapshot)
    return snapshot
