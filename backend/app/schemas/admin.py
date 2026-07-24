from __future__ import annotations
from datetime import datetime
from typing import Annotated, Optional, List, Literal
from pydantic import BaseModel, Field, AfterValidator
from ..api.utils import (
    normalize_season_start_game_number,
    normalize_text_moderation_whitelist,
    normalize_text_moderation_blacklist,
)

SeasonStartCsv = Annotated[str, AfterValidator(normalize_season_start_game_number)]
TextModerationWhitelistCsv = Annotated[str, AfterValidator(normalize_text_moderation_whitelist)]
TextModerationBlacklistCsv = Annotated[str, AfterValidator(normalize_text_moderation_blacklist)]


class SiteSettingsOut(BaseModel):
    registration_enabled: bool
    rooms_can_create: bool
    rooms_can_enter: bool
    games_can_start: bool
    streams_can_start: bool
    chat_open_enabled: bool
    chat_messages_enabled: bool
    verification_restrictions: bool
    admin_banner_text: str
    admin_banner_link: str
    donation_url: str
    rooms_limit_global: int
    rooms_limit_per_user: int
    rooms_empty_ttl_seconds: int
    rooms_single_ttl_minutes: int
    season_start_game_number: str
    text_moderation_whitelist: str
    text_moderation_blacklist: str
    blacklist_users_limit: int
    self_speech_finish_enabled: bool


class SiteSettingsUpdateIn(BaseModel):
    registration_enabled: Optional[bool] = None
    rooms_can_create: Optional[bool] = None
    rooms_can_enter: Optional[bool] = None
    games_can_start: Optional[bool] = None
    streams_can_start: Optional[bool] = None
    chat_open_enabled: Optional[bool] = None
    chat_messages_enabled: Optional[bool] = None
    verification_restrictions: Optional[bool] = None
    admin_banner_text: Optional[str] = Field(default=None, max_length=2048)
    admin_banner_link: Optional[str] = Field(default=None, max_length=2048)
    donation_url: Optional[str] = Field(default=None, max_length=2048)
    rooms_limit_global: Optional[int] = Field(default=None, ge=1)
    rooms_limit_per_user: Optional[int] = Field(default=None, ge=1)
    rooms_empty_ttl_seconds: Optional[int] = Field(default=None, ge=1)
    rooms_single_ttl_minutes: Optional[int] = Field(default=None, ge=1)
    season_start_game_number: Optional[SeasonStartCsv] = Field(default=None, min_length=1, max_length=255)
    text_moderation_whitelist: Optional[TextModerationWhitelistCsv] = Field(default=None, max_length=4096)
    text_moderation_blacklist: Optional[TextModerationBlacklistCsv] = Field(default=None, max_length=4096)
    blacklist_users_limit: Optional[int] = Field(default=None, ge=0)
    self_speech_finish_enabled: Optional[bool] = None


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
    wink_spot_chance_percent: int


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
    wink_spot_chance_percent: Optional[int] = Field(default=None, ge=0, le=100)


class AdminSettingsOut(BaseModel):
    site: SiteSettingsOut
    game: GameSettingsOut


class AdminSettingsUpdateIn(BaseModel):
    site: Optional[SiteSettingsUpdateIn] = None
    game: Optional[GameSettingsUpdateIn] = None


class AdminUpdateNotificationIn(BaseModel):
    title: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=4096)


class AdminUpdateNotificationOut(BaseModel):
    sent_count: int


class PublicSettingsOut(BaseModel):
    registration_enabled: bool
    rooms_can_create: bool
    rooms_can_enter: bool
    games_can_start: bool
    streams_can_start: bool
    chat_open_enabled: bool
    chat_messages_enabled: bool
    verification_restrictions: bool
    admin_banner_text: str
    admin_banner_link: str
    donation_url: str
    rooms_limit_global: int
    game_min_ready_players: int
    winks_limit: int
    knocks_limit: int
    wink_spot_chance_percent: int
    season_start_game_number: str
    self_speech_finish_enabled: bool


class RegistrationsPoint(BaseModel):
    date: str
    count: int


class OnlineUserOut(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None


class PeriodStatsOut(BaseModel):
    games: int
    rooms: int
    stream_minutes: int


class AdminGamesEndAllOut(BaseModel):
    ended: int
    skipped: int
    failed: int


class SiteStatsOut(BaseModel):
    total_users: int
    avatars_count: int
    avatars_bytes: int
    images_count: int
    images_bytes: int
    registrations: List[RegistrationsPoint]
    games_by_day: List[RegistrationsPoint]
    active_users_by_day: List[RegistrationsPoint]
    registrations_monthly: List[RegistrationsPoint]
    games_monthly: List[RegistrationsPoint]
    active_users_monthly: List[RegistrationsPoint]
    total_rooms: int
    total_games: int
    total_stream_minutes: int
    active_room_users: int
    online_users: int
    online_users_list: List[OnlineUserOut]
    last_month: PeriodStatsOut


class AdminLogOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    role: Optional[str] = None
    deleted_at: Optional[datetime] = None
    action: str
    details: str
    created_at: datetime


class AdminLogsOut(BaseModel):
    total: int
    items: List[AdminLogOut]


class AdminLogActionsOut(BaseModel):
    actions: List[str]


class AdminContactRequestOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    role: Optional[str] = None
    deleted_at: Optional[datetime] = None
    contact: str
    topic: str
    text: str
    created_at: datetime


class AdminContactRequestsOut(BaseModel):
    total: int
    items: List[AdminContactRequestOut]


class AdminContactRequestReplyIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


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


class AdminSanctionListItemOut(BaseModel):
    id: int
    user_id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    role: Optional[str] = None
    deleted_at: Optional[datetime] = None
    kind: Literal["timeout", "ban", "suspend"]
    status: Literal["active", "expired_auto", "revoked"]
    issued_at: datetime
    finished_at: Optional[datetime] = None
    issued_by_id: Optional[int] = None
    issued_by_name: Optional[str] = None
    issued_by_display: str
    revoked_by_id: Optional[int] = None
    revoked_by_name: Optional[str] = None
    revoked_by_display: Optional[str] = None
    duration_seconds: Optional[int] = None
    served_seconds: int
    hosted_workoff_seconds: Optional[int] = None
    reason: Optional[str] = None
    description: Optional[str] = None


class AdminSanctionsOut(BaseModel):
    total: int
    items: List[AdminSanctionListItemOut] = Field(default_factory=list)


class AdminRoomUserStat(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    minutes: int


class AdminRoomGameOut(BaseModel):
    number: int
    result: Literal["red", "black", "draw", "active"]
    minutes: int


class AdminRoomOut(BaseModel):
    id: int
    creator: int
    creator_name: str
    creator_avatar_name: Optional[str] = None
    creator_role: Optional[str] = None
    creator_deleted_at: Optional[datetime] = None
    title: str
    user_limit: int
    privacy: str
    anonymity: Literal["visible", "hidden"] = "visible"
    created_at: datetime
    deleted_at: Optional[datetime] = None
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


class AdminGameActionFieldOut(BaseModel):
    label: str
    value: str


class AdminGameActionOut(BaseModel):
    order: int
    type: str
    occurred_at: Optional[datetime] = None
    title: str
    summary: str
    fields: List[AdminGameActionFieldOut] = Field(default_factory=list)


AdminGameResult = Literal["red", "black", "draw"]


class AdminGameActionsOut(BaseModel):
    id: int
    number: int
    result: AdminGameResult
    ppk_target_user_id: Optional[int] = None
    items: List[AdminGameActionOut] = Field(default_factory=list)


class AdminGameResultUpdateIn(BaseModel):
    result: AdminGameResult


class AdminGameResultOut(BaseModel):
    id: int
    number: int
    result: AdminGameResult


class AdminGamePpkUpdateIn(BaseModel):
    target_user_id: Optional[int] = None


class AdminGamePpkOut(BaseModel):
    id: int
    number: int
    target_user_id: Optional[int] = None


class AdminGameFoulRemovalsUpdateIn(BaseModel):
    removed_user_ids: List[int] = Field(default_factory=list)


class AdminGameFoulRemovalsOut(BaseModel):
    id: int
    number: int
    removed_user_ids: List[int] = Field(default_factory=list)
    ppk_target_user_id: Optional[int] = None


class AdminUserOut(BaseModel):
    id: int
    tg_id: Optional[int] = None
    tg_nick: Optional[str] = None
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    role: str
    registered_at: datetime
    last_visit_at: Optional[datetime] = None
    last_game_at: Optional[datetime] = None
    last_game_id: Optional[int] = None
    online: bool = False
    last_room_id: Optional[int] = None
    last_spectator_room_id: Optional[int] = None
    games_played: int = 0
    games_hosted: int = 0
    room_minutes: int = 0
    stream_minutes: int = 0
    spectator_minutes: int = 0
    deleted_at: Optional[datetime] = None
    timeouts_count: int
    bans_count: int
    suspends_count: int


class AdminUsersOut(BaseModel):
    total: int
    items: List[AdminUserOut]


class AdminSubscriptionOut(BaseModel):
    user_id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    role: Optional[str] = None
    deleted_at: Optional[datetime] = None
    starts_at: datetime
    ends_at: datetime
    is_active: bool
    profile_theme_color: Optional[str] = None
    profile_theme_icon: Optional[str] = None


class AdminSubscriptionsOut(BaseModel):
    items: List[AdminSubscriptionOut] = Field(default_factory=list)


class AdminSubscriptionDurationIn(BaseModel):
    months: int = Field(default=0, ge=0, le=240)
    days: int = Field(default=0, ge=0, le=31)


class AdminSubscriptionCreateIn(AdminSubscriptionDurationIn):
    user_id: int = Field(ge=1)


class AdminSanctionTimedIn(BaseModel):
    months: int = Field(default=0, ge=0, le=240)
    days: int = Field(default=0, ge=0, le=31)
    hours: int = Field(default=0, ge=0, le=23)
    reason: str = Field(min_length=1, max_length=1024)
    description: str = Field(min_length=1, max_length=2048)


class AdminSanctionDurationAdjustIn(BaseModel):
    months: int = Field(default=0, ge=0, le=240)
    days: int = Field(default=0, ge=0, le=31)
    hours: int = Field(default=0, ge=0, le=23)


class AdminSanctionBanIn(BaseModel):
    reason: str = Field(min_length=1, max_length=1024)
    description: str = Field(min_length=1, max_length=2048)


class AdminUserRoleIn(BaseModel):
    role: Literal["moder", "user"]


class AdminUserRoleOut(BaseModel):
    id: int
    role: str


class AdminUserNameOut(BaseModel):
    id: int
    username: str
