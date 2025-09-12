from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class Ok(BaseModel):
    status: str = Field(default="ok")


class UserOut(BaseModel):
    id: int
    username: Optional[str] = None
    photo_url: Optional[str] = None
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


class TokenOut(BaseModel):
    access_token: str
    token_type: str = Field(default="bearer")
    user: UserOut


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
