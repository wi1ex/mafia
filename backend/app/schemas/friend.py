from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field

FriendStatus = Literal["self", "friends", "outgoing", "incoming", "none"]
FriendListKind = Literal["incoming", "outgoing", "online", "offline"]


class FriendStatusOut(BaseModel):
    status: FriendStatus


class FriendsListItemOut(BaseModel):
    kind: FriendListKind
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    role: Optional[str] = None
    theme_color: Optional[str] = None
    theme_icon: Optional[str] = None
    online: Optional[bool] = None
    closeness: Optional[int] = None
    room_id: Optional[int] = None
    room_title: Optional[str] = None
    room_in_game: Optional[bool] = None
    in_current_room: Optional[bool] = None
    in_active_game_as_alive_player: Optional[bool] = None
    in_active_game_as_host: Optional[bool] = None
    room_invited: Optional[bool] = None
    tg_invite_cooldown_active: Optional[bool] = None
    ban_active: Optional[bool] = None
    timeout_active: Optional[bool] = None
    telegram_verified: Optional[bool] = None
    tg_invites_enabled: Optional[bool] = None
    requested_at: Optional[datetime] = None


class FriendsListOut(BaseModel):
    items: List[FriendsListItemOut] = Field(default_factory=list)


class FriendIncomingCountOut(BaseModel):
    count: int = 0


class FriendInviteIn(BaseModel):
    user_id: int
    room_id: int
