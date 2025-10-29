from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class RoomCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=32)
    user_limit: int = Field(ge=2, le=12, default=12)
    privacy: Literal["open", "private"] = Field(default="open")


class RoomIdOut(BaseModel):
    id: int


class RoomInfoMemberOut(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None


class RoomInfoOut(BaseModel):
    members: List[RoomInfoMemberOut] = Field(default_factory=list)


class RoomAccessOut(BaseModel):
    access: Literal["approved", "pending", "none"]
