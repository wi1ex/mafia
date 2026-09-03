from __future__ import annotations
from datetime import datetime
from typing import Annotated, Optional, List, Literal
from pydantic import AfterValidator, BaseModel, Field, field_validator, model_validator
from ..api.utils import (
    normalize_season_start_game_number,
    normalize_text_moderation_whitelist,
    normalize_text_moderation_blacklist,
)

SeasonStartCsv = Annotated[str, AfterValidator(normalize_season_start_game_number)]
TextModerationWhitelistCsv = Annotated[str, AfterValidator(normalize_text_moderation_whitelist)]
TextModerationBlacklistCsv = Annotated[str, AfterValidator(normalize_text_moderation_blacklist)]

SanctionBadgeKey = Literal["ban", "tm1", "tm2", "tm3", "tm4", "ot1", "ot2", "ot3", "ot4"]


class SanctionRuleItem(BaseModel):
    text: str = Field(min_length=1, max_length=1024)
    badge: SanctionBadgeKey | None = None

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("rule_text_required")

        return normalized


class SanctionRulesSection(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9-]*$")
    title: str = Field(min_length=1, max_length=255)
    rules: List[SanctionRuleItem] = Field(min_length=1, max_length=100)

    @field_validator("id", "title")
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("rule_section_value_required")

        return normalized


class SanctionRulesOut(BaseModel):
    sections: List[SanctionRulesSection] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_unique_section_ids(self):
        ids = [section.id for section in self.sections]
        if len(ids) != len(set(ids)):
            raise ValueError("rule_section_ids_must_be_unique")

        return self


class SanctionRulesUpdateIn(SanctionRulesOut):
    pass


class SiteSettingsOut(BaseModel):
    registration_enabled: bool
    rooms_can_create: bool
    rooms_can_enter: bool
    games_can_start: bool
    rating_enabled: bool
    streams_can_start: bool
    chat_open_enabled: bool
    chat_messages_enabled: bool
    verification_restrictions: bool
    admin_banner_text: str
    admin_banner_link: str
    home_carousel_banner_key: Optional[str] = None
    donation_url: str
    rooms_limit_global: int
    rooms_limit_per_user: int
    spectators_limit: int
    rooms_empty_ttl_seconds: int
    rooms_single_ttl_minutes: int
    season_start_game_number: str
    text_moderation_whitelist: str
    text_moderation_blacklist: str
    senior_moderator_user_id: Optional[int] = None


class SiteSettingsUpdateIn(BaseModel):
    registration_enabled: Optional[bool] = None
    rooms_can_create: Optional[bool] = None
    rooms_can_enter: Optional[bool] = None
    games_can_start: Optional[bool] = None
    rating_enabled: Optional[bool] = None
    streams_can_start: Optional[bool] = None
    chat_open_enabled: Optional[bool] = None
    chat_messages_enabled: Optional[bool] = None
    verification_restrictions: Optional[bool] = None
    admin_banner_text: Optional[str] = Field(default=None, max_length=2048)
    admin_banner_link: Optional[str] = Field(default=None, max_length=2048)
    donation_url: Optional[str] = Field(default=None, max_length=2048)
    rooms_limit_global: Optional[int] = Field(default=None, ge=1)
    rooms_limit_per_user: Optional[int] = Field(default=None, ge=1)
    spectators_limit: Optional[int] = Field(default=None, ge=0, le=100)
    rooms_empty_ttl_seconds: Optional[int] = Field(default=None, ge=1)
    rooms_single_ttl_minutes: Optional[int] = Field(default=None, ge=1)
    season_start_game_number: Optional[SeasonStartCsv] = Field(default=None, min_length=1, max_length=255)
    text_moderation_whitelist: Optional[TextModerationWhitelistCsv] = Field(default=None, max_length=4096)
    text_moderation_blacklist: Optional[TextModerationBlacklistCsv] = Field(default=None, max_length=4096)
    senior_moderator_user_id: Optional[int] = Field(default=None, ge=1)


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
    game_roles_reveal_seconds: int


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
    game_roles_reveal_seconds: Optional[int] = Field(default=None, ge=1)


class AdminSettingsOut(BaseModel):
    site: SiteSettingsOut
    game: GameSettingsOut


class AdminSettingsUpdateIn(BaseModel):
    site: Optional[SiteSettingsUpdateIn] = None
    game: Optional[GameSettingsUpdateIn] = None


class GameScoringSettingsOut(BaseModel):
    additional_points_min: float
    additional_points_max: float
    fourth_foul: float
    fourth_foul_lost: float
    tech_foul: float
    second_tech_foul_lost: float
    suicide: float
    suicide_lost: float
    best_move_black_0: float
    best_move_black_1: float
    best_move_black_2: float
    best_move_black_3: float
    night_shoot_miss: float
    night_shoot_miss_terminal: float
    vote_opponent_team: float
    vote_red_terminal: float
    vote_red_terminal_3v3: float
    black_win_3v3: float
    vote_lift_same_team: float
    vote_lift_opponent_team: float
    nomination_black_prevents_black_win: float
    nomination_red_last_hope: float
    black_day_under_seven: float
    night_opinion_correct: float
    night_opinion_wrong: float
    farewell_red_correct: float
    farewell_red_wrong: float
    farewell_black_correct: float
    farewell_black_wrong: float
    farewell_black_named_red: float
    farewell_claimant_black_named_red: float
    fourth_foul_label: str
    fourth_foul_lost_label: str
    tech_foul_label: str
    second_tech_foul_lost_label: str
    suicide_label: str
    suicide_lost_label: str
    best_move_black_0_label: str
    best_move_black_1_label: str
    best_move_black_2_label: str
    best_move_black_3_label: str
    night_shoot_miss_label: str
    night_shoot_miss_terminal_label: str
    vote_opponent_team_label: str
    vote_red_terminal_label: str
    vote_red_terminal_3v3_label: str
    black_win_3v3_label: str
    vote_lift_same_team_label: str
    vote_lift_opponent_team_label: str
    nomination_black_prevents_black_win_label: str
    nomination_red_last_hope_label: str
    black_day_under_seven_label: str
    night_opinion_correct_label: str
    night_opinion_wrong_label: str
    farewell_red_correct_label: str
    farewell_red_wrong_label: str
    farewell_black_correct_label: str
    farewell_black_wrong_label: str
    farewell_black_named_red_label: str
    farewell_claimant_black_named_red_label: str


class GameScoringSettingsUpdateIn(BaseModel):
    additional_points_min: Optional[float] = Field(default=None, ge=-10, le=10)
    additional_points_max: Optional[float] = Field(default=None, ge=-10, le=10)
    fourth_foul: Optional[float] = Field(default=None, ge=-10, le=10)
    fourth_foul_lost: Optional[float] = Field(default=None, ge=-10, le=10)
    tech_foul: Optional[float] = Field(default=None, ge=-10, le=10)
    second_tech_foul_lost: Optional[float] = Field(default=None, ge=-10, le=10)
    suicide: Optional[float] = Field(default=None, ge=-10, le=10)
    suicide_lost: Optional[float] = Field(default=None, ge=-10, le=10)
    best_move_black_0: Optional[float] = Field(default=None, ge=-10, le=10)
    best_move_black_1: Optional[float] = Field(default=None, ge=-10, le=10)
    best_move_black_2: Optional[float] = Field(default=None, ge=-10, le=10)
    best_move_black_3: Optional[float] = Field(default=None, ge=-10, le=10)
    night_shoot_miss: Optional[float] = Field(default=None, ge=-10, le=10)
    night_shoot_miss_terminal: Optional[float] = Field(default=None, ge=-10, le=10)
    vote_opponent_team: Optional[float] = Field(default=None, ge=-10, le=10)
    vote_red_terminal: Optional[float] = Field(default=None, ge=-10, le=10)
    vote_red_terminal_3v3: Optional[float] = Field(default=None, ge=-10, le=10)
    black_win_3v3: Optional[float] = Field(default=None, ge=-10, le=10)
    vote_lift_same_team: Optional[float] = Field(default=None, ge=-10, le=10)
    vote_lift_opponent_team: Optional[float] = Field(default=None, ge=-10, le=10)
    nomination_black_prevents_black_win: Optional[float] = Field(default=None, ge=-10, le=10)
    nomination_red_last_hope: Optional[float] = Field(default=None, ge=-10, le=10)
    black_day_under_seven: Optional[float] = Field(default=None, ge=-10, le=10)
    night_opinion_correct: Optional[float] = Field(default=None, ge=-10, le=10)
    night_opinion_wrong: Optional[float] = Field(default=None, ge=-10, le=10)
    farewell_red_correct: Optional[float] = Field(default=None, ge=-10, le=10)
    farewell_red_wrong: Optional[float] = Field(default=None, ge=-10, le=10)
    farewell_black_correct: Optional[float] = Field(default=None, ge=-10, le=10)
    farewell_black_wrong: Optional[float] = Field(default=None, ge=-10, le=10)
    farewell_black_named_red: Optional[float] = Field(default=None, ge=-10, le=10)
    farewell_claimant_black_named_red: Optional[float] = Field(default=None, ge=-10, le=10)
    fourth_foul_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    fourth_foul_lost_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    tech_foul_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    second_tech_foul_lost_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    suicide_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    suicide_lost_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    best_move_black_0_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    best_move_black_1_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    best_move_black_2_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    best_move_black_3_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    night_shoot_miss_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    night_shoot_miss_terminal_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    vote_opponent_team_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    vote_red_terminal_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    vote_red_terminal_3v3_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    black_win_3v3_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    vote_lift_same_team_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    vote_lift_opponent_team_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    nomination_black_prevents_black_win_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    nomination_red_last_hope_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    black_day_under_seven_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    night_opinion_correct_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    night_opinion_wrong_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    farewell_red_correct_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    farewell_red_wrong_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    farewell_black_correct_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    farewell_black_wrong_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    farewell_black_named_red_label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    farewell_claimant_black_named_red_label: Optional[str] = Field(default=None, min_length=1, max_length=255)


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
    rating_enabled: bool
    streams_can_start: bool
    chat_open_enabled: bool
    chat_messages_enabled: bool
    verification_restrictions: bool
    admin_banner_text: str
    admin_banner_link: str
    home_carousel_banner_key: Optional[str] = None
    donation_url: str
    rooms_limit_global: int
    spectators_limit: int
    game_min_ready_players: int
    winks_limit: int
    knocks_limit: int
    wink_spot_chance_percent: int
    season_start_game_number: str
    senior_moderator_user_id: Optional[int] = None


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
AdminGameMode = Literal["normal", "rating"]


class AdminGameActionsOut(BaseModel):
    id: int
    number: int
    result: AdminGameResult
    mode: AdminGameMode = "normal"
    rating_mode_eligible: bool = False
    ppk_target_user_id: Optional[int] = None
    items: List[AdminGameActionOut] = Field(default_factory=list)


class AdminGameResultUpdateIn(BaseModel):
    result: AdminGameResult


class AdminGameResultOut(BaseModel):
    id: int
    number: int
    result: AdminGameResult


class AdminGameModeUpdateIn(BaseModel):
    mode: AdminGameMode


class AdminGameModeOut(BaseModel):
    id: int
    number: int
    mode: AdminGameMode = "normal"
    rating_mode_eligible: bool = False


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


class AdminSubscriptionCompensationOut(BaseModel):
    extended_count: int


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


class AdminSanctionReasonUpdateIn(BaseModel):
    reason: str = Field(min_length=1, max_length=1024)


class AdminSanctionBanIn(BaseModel):
    reason: str = Field(min_length=1, max_length=1024)
    description: str = Field(min_length=1, max_length=2048)


class AdminUserRoleIn(BaseModel):
    role: Literal["moder", "user"]


class AdminUserRoleOut(BaseModel):
    id: int
    role: str


class AdminUserAdditionalRoleIn(BaseModel):
    role: Literal["head_rate"]
    enabled: bool


class AdminUserAdditionalRolesOut(BaseModel):
    id: int
    additional_roles: List[str] = Field(default_factory=list)


class AdminUserNameOut(BaseModel):
    id: int
    username: str
