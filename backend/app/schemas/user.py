from datetime import datetime
from typing import Annotated, Optional, List, Literal
from pydantic import BaseModel, Field
from pydantic.functional_validators import BeforeValidator
from ..api.utils import sanitize_username_for_schema

UsernameClean = Annotated[str, BeforeValidator(sanitize_username_for_schema)]


class UserOut(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    role: str
    registered_at: Optional[datetime] = None
    telegram_verified: bool = False
    has_password: bool = False
    password_temp: bool = False
    protected_user: bool = False
    hotkeys_visible: bool = True
    tg_invites_enabled: bool = True
    subscription_active: bool = False
    subscription_started_at: Optional[datetime] = None
    subscription_until: Optional[datetime] = None
    profile_theme_color: Optional[str] = None
    profile_theme_icon: Optional[str] = None
    timeout_until: Optional[datetime] = None
    suspend_until: Optional[datetime] = None
    ban_active: bool = False
    in_active_game_as_alive_player: bool = False
    in_active_game_as_player: bool = False
    chat_unread_count: int = 0


class UserMiniProfileSanctionOut(BaseModel):
    kind: Literal["timeout", "ban", "suspend"]
    expires_at: Optional[datetime] = None


class UserMiniProfileFriendOut(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    friendship_started_at: Optional[datetime] = None


class UserMiniProfileOut(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    role: str
    deleted: bool = False
    registered_at: Optional[datetime] = None
    last_visit_at: Optional[datetime] = None
    last_game_at: Optional[datetime] = None
    last_game_id: Optional[int] = None
    online: bool = False
    subscription_active: bool = False
    profile_theme_color: Optional[str] = None
    profile_theme_icon: Optional[str] = None
    friend_status: Literal["self", "friends", "outgoing", "incoming", "none"] = "none"
    friends_count: int = 0
    admin_friends: Optional[List[UserMiniProfileFriendOut]] = None
    active_sanction: Optional[UserMiniProfileSanctionOut] = None


class UserNicknameHistoryOut(BaseModel):
    items: List[str] = Field(default_factory=list)


class UserTopPlayerOut(BaseModel):
    id: int
    username: Optional[str] = None
    games_together: int = 0


class UserRoleStatsOut(BaseModel):
    games: int = 0
    wins: int = 0


class UserBestMoveStatsOut(BaseModel):
    first_killed_total: int = 0
    marks_black_0: int = 0
    marks_black_1: int = 0
    marks_black_2: int = 0
    marks_black_3: int = 0


class UserGameStatsOut(BaseModel):
    games_played: int = 0
    games_won: int = 0
    games_hosted: int = 0
    don_first_night_find_percent: float = 0.0
    vote_leave_day12_percent: float = 0.0
    vote_out_don_day12_count: int = 0
    vote_out_sheriff_day12_count: int = 0
    foul_removed_count: int = 0
    ppk_removed_count: int = 0
    vote_for_red_on_black_win_count: int = 0
    farewell_success_percent: float = 0.0
    best_win_streak: int = 0
    best_loss_streak: int = 0
    role_citizen: UserRoleStatsOut
    role_sheriff: UserRoleStatsOut
    role_don: UserRoleStatsOut
    role_mafia: UserRoleStatsOut
    best_move: UserBestMoveStatsOut
    top_players: List[UserTopPlayerOut] = Field(default_factory=list)


class UserStatsOut(BaseModel):
    rooms_created: int = 0
    games_in_my_rooms: int = 0
    room_minutes: int = 0
    stream_minutes: int = 0
    spectator_minutes: int = 0
    game: UserGameStatsOut


class UserSanctionOut(BaseModel):
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


class UserSanctionsOut(BaseModel):
    items: List[UserSanctionOut]


class GameHistoryHostOut(BaseModel):
    id: Optional[int] = None
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    auto: bool = False


class GameHistoryFarewellItemOut(BaseModel):
    slot: int
    verdict: Literal["citizen", "mafia"]


class GameHistoryNightCheckItemOut(BaseModel):
    slot: int
    verdict: Literal["citizen", "mafia", "sheriff"]


class GameHistorySlotOut(BaseModel):
    slot: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    profile_role: Optional[str] = None
    deleted: bool = False
    role: Optional[Literal["citizen", "mafia", "don", "sheriff"]] = None
    points: int = 0
    mmr: int = 0
    leave_day: Optional[int] = None
    leave_reason: Optional[Literal["vote", "foul", "suicide", "night"]] = None
    leave_ppk: bool = False
    voted_by_slots: List[int] = Field(default_factory=list)
    best_move_slots: List[int] = Field(default_factory=list)
    farewell: List[GameHistoryFarewellItemOut] = Field(default_factory=list)
    night_checks: List[GameHistoryNightCheckItemOut] = Field(default_factory=list)


class GameHistoryItemOut(BaseModel):
    id: int
    number: int
    head: GameHistoryHostOut
    result: Literal["red", "black", "draw"]
    has_ppk: bool = False
    player_role: Optional[Literal["citizen", "mafia", "don", "sheriff"]] = None
    player_points: Optional[int] = None
    player_mmr: Optional[int] = None
    black_alive_at_finish: int = 0
    started_at: datetime
    finished_at: datetime
    duration_seconds: int = 0
    slots: List[GameHistorySlotOut] = Field(default_factory=list)


class UserGamesHistoryOut(BaseModel):
    total: int = 0
    page: int = 1
    pages: int = 1
    per_page: int = 20
    total_red_wins: int = 0
    total_black_wins: int = 0
    items: List[GameHistoryItemOut] = Field(default_factory=list)


class UsernameUpdateIn(BaseModel):
    username: UsernameClean = Field(min_length=2, max_length=20)


class UsernameUpdateOut(BaseModel):
    username: str


class AvatarUploadOut(BaseModel):
    avatar_name: Optional[str] = None


class ChatImageUploadOut(BaseModel):
    image_object_key: str


class ChatImagePresignIn(BaseModel):
    content_type: str = Field(min_length=1, max_length=100)


class ChatImagePresignOut(BaseModel):
    image_object_key: str
    upload_url: str
    expires_in: int
    content_type: str
    upload_method: Literal["PUT", "POST"] = "PUT"
    upload_fields: dict[str, str] = Field(default_factory=dict)


class ChatMentionUserOut(BaseModel):
    id: int
    username: str
    avatar_name: Optional[str] = None


class ChatMentionSearchOut(BaseModel):
    items: List[ChatMentionUserOut] = Field(default_factory=list)


class UserUiPrefsIn(BaseModel):
    hotkeys_visible: Optional[bool] = None
    tg_invites_enabled: Optional[bool] = None


class UserUiPrefsOut(BaseModel):
    hotkeys_visible: bool
    tg_invites_enabled: bool


class SupportLinkClickIn(BaseModel):
    source: Optional[str] = Field(default=None, max_length=64)
    site_id: Optional[str] = Field(default=None, max_length=64)
    site_name: Optional[str] = Field(default=None, max_length=128)
    url: Optional[str] = Field(default=None, max_length=512)


class UserProfileThemeIn(BaseModel):
    color: str = Field(min_length=1, max_length=32)
    icon: Optional[str] = Field(default=None, max_length=32)


class UserProfileThemeOut(BaseModel):
    subscription_active: bool
    subscription_started_at: Optional[datetime] = None
    subscription_until: Optional[datetime] = None
    profile_theme_color: Optional[str] = None
    profile_theme_icon: Optional[str] = None


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=8, max_length=32)
    new_password: str = Field(min_length=8, max_length=32)
