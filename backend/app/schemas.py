from __future__ import annotations
from typing import Optional, Dict, TypedDict, List, Literal
from pydantic import BaseModel, ConfigDict, Field


class Ok(BaseModel):
    status: str = Field(default="ok")


class UserOut(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    role: str


class Identity(TypedDict):
    id: int
    username: str
    role: str


class TelegramAuthIn(BaseModel):
    id: int
    auth_date: int
    hash: str
    username: Optional[str] = None
    photo_url: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: Optional[str] = None
    allows_write_to_pm: Optional[bool] = None
    model_config = ConfigDict(extra='allow')


class AccessTokenOut(BaseModel):
    access_token: str
    token_type: str = Field(default="bearer")
    sid: str


class RoomCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=32)
    user_limit: int = Field(ge=2, le=12, default=12)
    privacy: Literal["open", "private"] = Field(default="open")


class RoomOut(BaseModel):
    id: int
    title: str
    user_limit: int
    privacy: Literal["open", "private"]
    creator: int
    creator_name: str
    created_at: str


class JoinAck(TypedDict, total=False):
    ok: bool
    error: str
    status: int
    room_id: int
    token: str
    snapshot: Dict[str, Dict[str, str]]
    self_pref: Dict[str, str]
    positions: Dict[str, int]
    blocked: Dict[str, Dict[str, str]]
    roles: Dict[str, str]
    profiles: Dict[str, Dict[str, Optional[str]]]
    screen_owner: int
    pending: bool


class ErrorOut(BaseModel):
    detail: str


class RoomListItem(TypedDict):
    id: int
    title: str
    user_limit: int
    creator: int
    creator_name: str
    created_at: str
    occupancy: int


class RoomsListAck(TypedDict):
    ok: bool
    rooms: List[RoomListItem]


class StateAck(TypedDict):
    ok: bool


class ModerateAck(TypedDict, total=False):
    ok: bool
    status: int
    error: str
    applied: Dict[str, str]
    forced_off: Dict[str, str]


class ScreenAck(TypedDict, total=False):
    ok: bool
    on: bool
    error: str
    status: int
    owner: int


class RoomInfoMemberOut(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None


class RoomInfoOut(BaseModel):
    members: List[RoomInfoMemberOut] = Field(default_factory=list)


class UsernameUpdateIn(BaseModel):
    username: str = Field(min_length=2, max_length=20)


class AvatarUploadOut(BaseModel):
    avatar_name: Optional[str] = None


class RoomAccessOut(BaseModel):
    privacy: Literal["open", "private"]
    access: Literal["approved", "pending", "none"]


class NotifOut(BaseModel):
    id: int
    text: str
    created_at: str
    read: bool = False


class NotifsListOut(BaseModel):
    items: List[NotifOut]
    unread_count: int


class MarkReadIn(BaseModel):
    ids: List[int] = Field(default_factory=list)
    all_before_id: Optional[int] = None
