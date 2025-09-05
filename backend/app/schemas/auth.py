from __future__ import annotations
from pydantic import BaseModel, HttpUrl
from typing import Optional

class TelegramAuthIn(BaseModel):
    id: int
    username: Optional[str] = None
    photo_url: Optional[HttpUrl] = None
    auth_date: int
    hash: str

class UserOut(BaseModel):
    id: int
    username: Optional[str] = None
    photo_url: Optional[str] = None
    role: str

class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
