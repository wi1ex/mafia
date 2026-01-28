from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class SiteSettingsOut(BaseModel):
    registration_enabled: bool
    rooms_can_create: bool
    rooms_can_enter: bool
    games_can_start: bool
    streams_can_start: bool
    rooms_limit_global: int
    rooms_limit_per_user: int
    rooms_empty_ttl_seconds: int
    season_start_game_number: int


class SiteSettingsUpdateIn(BaseModel):
    registration_enabled: Optional[bool] = None
    rooms_can_create: Optional[bool] = None
    rooms_can_enter: Optional[bool] = None
    games_can_start: Optional[bool] = None
    streams_can_start: Optional[bool] = None
    rooms_limit_global: Optional[int] = Field(default=None, ge=1)
    rooms_limit_per_user: Optional[int] = Field(default=None, ge=1)
    rooms_empty_ttl_seconds: Optional[int] = Field(default=None, ge=1)
    season_start_game_number: Optional[int] = Field(default=None, ge=1)


class GameSettingsOut(BaseModel):
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


class GameSettingsUpdateIn(BaseModel):
    game_min_ready_players: Optional[int] = Field(default=None, ge=1)
    role_pick_seconds: Optional[int] = Field(default=None, ge=1)
    mafia_talk_seconds: Optional[int] = Field(default=None, ge=1)
    player_talk_seconds: Optional[int] = Field(default=None, ge=1)
    player_talk_short_seconds: Optional[int] = Field(default=None, ge=1)
    player_foul_seconds: Optional[int] = Field(default=None, ge=1)
    night_action_seconds: Optional[int] = Field(default=None, ge=1)
    vote_seconds: Optional[int] = Field(default=None, ge=1)
    winks_limit: Optional[int] = Field(default=None, ge=0)
    knocks_limit: Optional[int] = Field(default=None, ge=0)


class AdminSettingsOut(BaseModel):
    site: SiteSettingsOut
    game: GameSettingsOut


class AdminSettingsUpdateIn(BaseModel):
    site: Optional[SiteSettingsUpdateIn] = None
    game: Optional[GameSettingsUpdateIn] = None


class PublicSettingsOut(BaseModel):
    registration_enabled: bool
    rooms_can_create: bool
    rooms_can_enter: bool
    games_can_start: bool
    streams_can_start: bool
    game_min_ready_players: int
    winks_limit: int
    knocks_limit: int
    season_start_game_number: int


class RegistrationsPoint(BaseModel):
    date: str
    count: int


class OnlineUserOut(BaseModel):
    id: int
    username: Optional[str] = None


class PeriodStatsOut(BaseModel):
    games: int
    online_users: int
    rooms: int
    stream_minutes: int


class SiteStatsOut(BaseModel):
    total_users: int
    registrations: List[RegistrationsPoint]
    registrations_monthly: List[RegistrationsPoint]
    total_rooms: int
    total_games: int
    total_stream_minutes: int
    active_rooms: int
    active_room_users: int
    online_users: int
    online_users_list: List[OnlineUserOut]
    last_day: PeriodStatsOut
    last_month: PeriodStatsOut


class AdminLogOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    action: str
    details: str
    created_at: datetime


class AdminLogsOut(BaseModel):
    total: int
    items: List[AdminLogOut]


class AdminLogActionsOut(BaseModel):
    actions: List[str]


class AdminSanctionOut(BaseModel):
    id: int
    kind: Literal["timeout", "ban", "suspend"]
    reason: Optional[str] = None
    issued_at: datetime
    issued_by_id: Optional[int] = None
    issued_by_name: Optional[str] = None
    duration_seconds: Optional[int] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by_id: Optional[int] = None
    revoked_by_name: Optional[str] = None


class AdminRoomUserStat(BaseModel):
    id: int
    username: Optional[str] = None
    minutes: int


class AdminRoomGameOut(BaseModel):
    number: int
    result: Literal["red", "black", "draw"]
    minutes: int


class AdminRoomOut(BaseModel):
    id: int
    creator: int
    creator_name: str
    creator_avatar_name: Optional[str] = None
    title: str
    user_limit: int
    privacy: str
    created_at: datetime
    deleted_at: Optional[datetime] = None
    game_mode: str
    game_format: str
    spectators_limit: int
    nominate_mode: str
    break_at_zero: bool
    lift_at_zero: bool
    lift_3x: bool
    wink_knock: bool
    farewell_wills: bool
    music: bool
    visitors_count: int
    visitors: List[AdminRoomUserStat]
    spectators_count: int
    spectators: List[AdminRoomUserStat]
    games: List[AdminRoomGameOut]
    stream_minutes: int
    streamers: List[AdminRoomUserStat]
    has_stream: bool


class AdminRoomsOut(BaseModel):
    total: int
    items: List[AdminRoomOut]


class AdminUserOut(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    role: str
    registered_at: datetime
    last_login_at: datetime
    last_visit_at: datetime
    deleted_at: Optional[datetime] = None
    rooms_created: int
    room_minutes: int
    stream_minutes: int
    games_played: int
    games_hosted: int
    spectator_minutes: int
    timeout_active: bool
    timeout_until: Optional[datetime] = None
    ban_active: bool
    suspend_active: bool
    suspend_until: Optional[datetime] = None
    timeouts_count: int
    bans_count: int
    suspends_count: int
    timeouts: List[AdminSanctionOut]
    bans: List[AdminSanctionOut]
    suspends: List[AdminSanctionOut]


class AdminUsersOut(BaseModel):
    total: int
    items: List[AdminUserOut]


class AdminSanctionTimedIn(BaseModel):
    months: int = Field(default=0, ge=0, le=24)
    days: int = Field(default=0, ge=0, le=365)
    hours: int = Field(default=0, ge=0, le=720)
    minutes: int = Field(default=0, ge=0, le=60 * 24 * 31)
    reason: str = Field(min_length=1, max_length=1024)


class AdminSanctionBanIn(BaseModel):
    reason: str = Field(min_length=1, max_length=1024)


class AdminUserRoleIn(BaseModel):
    role: Literal["admin", "user"]


class AdminUserRoleOut(BaseModel):
    id: int
    role: str
