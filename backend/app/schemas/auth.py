from __future__ import annotations
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional

class TelegramAuthIn(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[HttpUrl] = None
    auth_date: int
    hash: str = Field(min_length=64, max_length=64)

class UserOut(BaseModel):
    id: int
    username: Optional[str] = None
    nickname: Optional[str] = None
    name: Optional[str] = None
    photo_url: Optional[str] = None
    role: str

class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class AuthPending(BaseModel):
    need_profile: bool = True
    session: str
    suggested_username: Optional[str] = None
    suggested_name: Optional[str] = None

class CompleteProfileIn(BaseModel):
    session: str
    nickname: str = Field(pattern=r"^[a-zA-Z0-9_]{3,32}$")
    name: str = Field(min_length=1, max_length=128)
