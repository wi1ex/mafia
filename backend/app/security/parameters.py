from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.settings import settings as core_settings
from ..models.settings import AppSettings
from ..api.utils import (
    parse_season_starts_or_default,
    season_starts_csv,
    normalize_admin_banner_text,
    normalize_admin_banner_link,
    normalize_season_start_value,
    build_app_settings_snapshot_defaults,
    build_app_settings_snapshot_from_row,
)


@dataclass(frozen=True)
class AppSettingsSnapshot:
    registration_enabled: bool
    rooms_can_create: bool
    rooms_can_enter: bool
    games_can_start: bool
    streams_can_start: bool
    verification_restrictions: bool
    admin_banner_text: str
    admin_banner_link: str
    rooms_limit_global: int
    rooms_limit_per_user: int
    rooms_empty_ttl_seconds: int
    rooms_single_ttl_minutes: int
    season_start_game_number: str
    season_start_game_numbers: tuple[int, ...]
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
_DEFAULT_SEASON_STARTS = parse_season_starts_or_default(core_settings.SEASON_START_GAME_NUMBER, default=(1,))
_DEFAULT_SEASON_START_CSV = season_starts_csv(_DEFAULT_SEASON_STARTS)
_SCHEMA_SYNCED = False


async def _ensure_settings_schema(session: AsyncSession) -> None:
    global _SCHEMA_SYNCED
    if _SCHEMA_SYNCED:
        return

    await session.execute(text("ALTER TABLE settings ADD COLUMN IF NOT EXISTS admin_banner_text VARCHAR(2048) NOT NULL DEFAULT '0'"))
    await session.execute(text("ALTER TABLE settings ADD COLUMN IF NOT EXISTS admin_banner_link VARCHAR(2048) NOT NULL DEFAULT '0'"))
    await session.execute(text("UPDATE settings SET admin_banner_text = '0' WHERE admin_banner_text IS NULL"))
    await session.execute(text("UPDATE settings SET admin_banner_link = '0' WHERE admin_banner_link IS NULL"))
    await session.commit()
    _SCHEMA_SYNCED = True


def get_cached_settings() -> AppSettingsSnapshot:
    return _CACHE or build_app_settings_snapshot_defaults(
        core_settings,
        default_starts=_DEFAULT_SEASON_STARTS,
        snapshot_cls=AppSettingsSnapshot,
    )


def set_cached_settings(snapshot: AppSettingsSnapshot) -> None:
    global _CACHE
    _CACHE = snapshot


async def ensure_app_settings(session: AsyncSession) -> AppSettings:
    await _ensure_settings_schema(session)
    row = await session.scalar(select(AppSettings).limit(1))
    if not row:
        defaults = build_app_settings_snapshot_defaults(
            core_settings,
            default_starts=_DEFAULT_SEASON_STARTS,
            snapshot_cls=AppSettingsSnapshot,
        )
        row = AppSettings(
            id=1,
            registration_enabled=defaults.registration_enabled,
            rooms_can_create=defaults.rooms_can_create,
            rooms_can_enter=defaults.rooms_can_enter,
            games_can_start=defaults.games_can_start,
            streams_can_start=defaults.streams_can_start,
            verification_restrictions=defaults.verification_restrictions,
            admin_banner_text=normalize_admin_banner_text(defaults.admin_banner_text),
            admin_banner_link=normalize_admin_banner_link(defaults.admin_banner_link),
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
    else:
        normalized_season_csv, _ = normalize_season_start_value(
            getattr(row, "season_start_game_number", None),
            default_starts=_DEFAULT_SEASON_STARTS,
        )
        current_season_csv = str(getattr(row, "season_start_game_number", "") or "").strip()
        if current_season_csv != normalized_season_csv:
            row.season_start_game_number = normalized_season_csv
            await session.commit()
            await session.refresh(row)

    set_cached_settings(
        build_app_settings_snapshot_from_row(
            row,
            default_starts=_DEFAULT_SEASON_STARTS,
            snapshot_cls=AppSettingsSnapshot,
        )
    )
    return row


async def refresh_app_settings(session: AsyncSession) -> AppSettingsSnapshot:
    row = await ensure_app_settings(session)
    snapshot = build_app_settings_snapshot_from_row(
        row,
        default_starts=_DEFAULT_SEASON_STARTS,
        snapshot_cls=AppSettingsSnapshot,
    )
    set_cached_settings(snapshot)
    return snapshot


def sync_cache_from_row(row: AppSettings) -> AppSettingsSnapshot:
    snapshot = build_app_settings_snapshot_from_row(
        row,
        default_starts=_DEFAULT_SEASON_STARTS,
        snapshot_cls=AppSettingsSnapshot,
    )
    set_cached_settings(snapshot)
    return snapshot
