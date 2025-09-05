from __future__ import annotations
from pydantic import BaseModel, Field, HttpUrl
from pydantic.config import ConfigDict
from typing import Optional

class TelegramAuthIn(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[HttpUrl] = None
    auth_date: int
    hash: str = Field(min_length=64, max_length=64)
    model_config = ConfigDict(extra='allow')

class UserOut(BaseModel):
    id: int
    username: Optional[str] = None
    photo_url: Optional[str] = None
    role: str

class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
