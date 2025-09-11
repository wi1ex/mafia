from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field

# common
class Ok(BaseModel):
    status: str = Field(default="ok")

# user
class UserOut(BaseModel):
    id: int
    username: Optional[str] = None
    photo_url: Optional[str] = None
    role: str

# auth
class TelegramAuthIn(BaseModel):
    id: int
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = Field(default="bearer")
    user: UserOut

# room
class RoomCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    user_limit: int = Field(ge=1, le=128, default=12)
    is_private: bool = False

class RoomOut(BaseModel):
    id: int
    title: str
    user_limit: int
    is_private: bool
    created_by_user_id: int
    created_at: str
    updated_at: str
    occupancy: int = 0
