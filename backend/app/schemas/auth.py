from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


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
    model_config = ConfigDict(extra="allow")


class AccessTokenOut(BaseModel):
    access_token: str
    token_type: str = Field(default="bearer")
    sid: str
