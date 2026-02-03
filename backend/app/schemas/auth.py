from typing import Optional
from pydantic import BaseModel, Field
from .user import UsernameClean


class AccessTokenOut(BaseModel):
    access_token: str
    token_type: str = Field(default="bearer")
    sid: str
    is_new: Optional[bool] = None


class PasswordLoginIn(BaseModel):
    username: UsernameClean = Field(min_length=2, max_length=20)
    password: str = Field(min_length=6, max_length=64)


class PasswordRegisterIn(BaseModel):
    username: UsernameClean = Field(min_length=2, max_length=20)
    password: str = Field(min_length=6, max_length=64)
    accept_rules: Optional[bool] | None = None


class BotVerifyIn(BaseModel):
    username: UsernameClean = Field(min_length=2, max_length=20)
    password: str = Field(min_length=6, max_length=64)
    telegram_id: int


class BotResetIn(BaseModel):
    telegram_id: int


class BotStatusIn(BaseModel):
    telegram_id: int


class BotStatusOut(BaseModel):
    verified: bool


class TempPasswordOut(BaseModel):
    temp_password: str
    username: str
