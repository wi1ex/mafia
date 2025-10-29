from typing import Optional
from pydantic import BaseModel, Field


class UserOut(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    role: str


class UsernameUpdateIn(BaseModel):
    username: str = Field(min_length=2, max_length=20)


class UsernameUpdateOut(BaseModel):
    username: str


class AvatarUploadOut(BaseModel):
    avatar_name: Optional[str] = None
