from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class GameParams(BaseModel):
    mode: Literal["normal", "rating"] = "normal"
    format: Literal["hosted", "nohost"] = "hosted"
    spectators_limit: int = Field(ge=0, le=10, default=0)
    vote_at_zero: bool = True
    vote_three: bool = True
    speech30_at_3_fouls: bool = True
    extra30_at_2_fouls: bool = True


class RoomCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=32)
    user_limit: int = Field(ge=2, le=12, default=12)
    privacy: Literal["open", "private"] = Field(default="open")
    game: Optional[GameParams] = Field(default_factory=GameParams)


class RoomIdOut(BaseModel):
    id: int


class RoomInfoMemberOut(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    screen: Optional[bool] = None


class RoomInfoOut(BaseModel):
    members: List[RoomInfoMemberOut] = Field(default_factory=list)
    game: Optional[GameParams] = None


class RoomAccessOut(BaseModel):
    access: Literal["approved", "pending", "none"]
