from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


FriendStatus = Literal["self", "friends", "outgoing", "incoming", "none"]


class FriendStatusOut(BaseModel):
    status: FriendStatus


class FriendItemOut(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    online: bool = False
    closeness: int = 0
    room_id: Optional[int] = None
    room_title: Optional[str] = None
    room_in_game: Optional[bool] = None


class FriendRequestOut(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    requested_at: Optional[datetime] = None


class FriendsListOut(BaseModel):
    online: List[FriendItemOut] = Field(default_factory=list)
    offline: List[FriendItemOut] = Field(default_factory=list)
    incoming: List[FriendRequestOut] = Field(default_factory=list)
    outgoing: List[FriendRequestOut] = Field(default_factory=list)


class FriendInviteIn(BaseModel):
    user_id: int
    room_id: int
