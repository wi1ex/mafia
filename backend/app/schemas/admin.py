from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class SiteSettingsOut(BaseModel):
    registration_enabled: bool
    rooms_can_create: bool
    games_can_start: bool
    rooms_limit_global: int
    rooms_limit_per_user: int


class SiteSettingsUpdateIn(BaseModel):
    registration_enabled: Optional[bool] = None
    rooms_can_create: Optional[bool] = None
    games_can_start: Optional[bool] = None
    rooms_limit_global: Optional[int] = Field(default=None, ge=1)
    rooms_limit_per_user: Optional[int] = Field(default=None, ge=1)


class GameSettingsOut(BaseModel):
    game_min_ready_players: int
    role_pick_seconds: int
    mafia_talk_seconds: int
    player_talk_seconds: int
    player_talk_short_seconds: int
    player_foul_seconds: int
    night_action_seconds: int
    vote_seconds: int


class GameSettingsUpdateIn(BaseModel):
    game_min_ready_players: Optional[int] = Field(default=None, ge=1)
    role_pick_seconds: Optional[int] = Field(default=None, ge=1)
    mafia_talk_seconds: Optional[int] = Field(default=None, ge=1)
    player_talk_seconds: Optional[int] = Field(default=None, ge=1)
    player_talk_short_seconds: Optional[int] = Field(default=None, ge=1)
    player_foul_seconds: Optional[int] = Field(default=None, ge=1)
    night_action_seconds: Optional[int] = Field(default=None, ge=1)
    vote_seconds: Optional[int] = Field(default=None, ge=1)


class AdminSettingsOut(BaseModel):
    site: SiteSettingsOut
    game: GameSettingsOut


class PublicSettingsOut(BaseModel):
    registration_enabled: bool
    rooms_can_create: bool
    games_can_start: bool
