import unicodedata
from datetime import datetime
from typing import Any, Optional, List, Literal
from pydantic import BaseModel, Field
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated

def _sanitize_username(v: Any) -> str:
    s = unicodedata.normalize("NFKC", str(v or ""))
    s = s.strip()
    return s

UsernameClean = Annotated[str, BeforeValidator(_sanitize_username)]


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
    timeout_until: Optional[datetime] = None
    suspend_until: Optional[datetime] = None
    ban_active: bool = False


class UserTopPlayerOut(BaseModel):
    id: int
    username: Optional[str] = None
    games_together: int = 0


class UserRoleStatsOut(BaseModel):
    games: int = 0
    wins: int = 0
    winrate_percent: float = 0.0


class UserBestMoveStatsOut(BaseModel):
    first_killed_total: int = 0
    marks_black_0: int = 0
    marks_black_1: int = 0
    marks_black_2: int = 0
    marks_black_3: int = 0


class UserGameStatsOut(BaseModel):
    games_played: int = 0
    games_won: int = 0
    winrate_percent: float = 0.0
    games_hosted: int = 0
    don_first_night_find_count: int = 0
    don_first_night_find_percent: float = 0.0
    vote_leave_day12_count: int = 0
    vote_leave_day12_percent: float = 0.0
    foul_removed_count: int = 0
    foul_removed_percent: float = 0.0
    vote_for_red_on_black_win_count: int = 0
    farewell_total: int = 0
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


class GameHistorySlotOut(BaseModel):
    slot: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    role: Optional[Literal["citizen", "mafia", "don", "sheriff"]] = None
    points: int = 0
    mmr: int = 0
    leave_day: Optional[int] = None
    leave_reason: Optional[Literal["vote", "foul", "suicide", "night"]] = None


class GameHistoryItemOut(BaseModel):
    id: int
    number: int
    head: GameHistoryHostOut
    result: Literal["red", "black", "draw"]
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
    items: List[GameHistoryItemOut] = Field(default_factory=list)


class UsernameUpdateIn(BaseModel):
    username: UsernameClean = Field(min_length=2, max_length=20)


class UsernameUpdateOut(BaseModel):
    username: str


class AvatarUploadOut(BaseModel):
    avatar_name: Optional[str] = None


class UserUiPrefsIn(BaseModel):
    hotkeys_visible: Optional[bool] = None
    tg_invites_enabled: Optional[bool] = None


class UserUiPrefsOut(BaseModel):
    hotkeys_visible: bool
    tg_invites_enabled: bool


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=8, max_length=32)
    new_password: str = Field(min_length=8, max_length=32)
