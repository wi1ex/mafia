from typing import Annotated, Optional, List, Literal
from datetime import datetime
from pydantic.functional_validators import BeforeValidator
from pydantic import BaseModel, Field, model_validator
from ..api.utils import sanitize_title_for_schema

Title = Annotated[str, BeforeValidator(sanitize_title_for_schema)]


class GameParams(BaseModel):
    mode: Literal["normal", "rating"] = "normal"
    spectators_limit: int = Field(ge=0, le=10, default=10)
    nominate_mode: Literal["players", "head"] = "players"
    tech_fouls: bool = Field(default=False)
    break_at_zero: bool = Field(default=True)
    lift_at_zero: bool = Field(default=True)
    lift_3x: bool = Field(default=True)
    first_shot_check: bool = Field(default=True)
    wink_knock: bool = Field(default=True)
    farewell_wills: bool = Field(default=True)
    music: bool = Field(default=True)

    @model_validator(mode="after")
    def apply_rating_rules(self) -> "GameParams":
        if self.mode == "rating":
            self.spectators_limit = 10
            self.nominate_mode = "players"
            self.tech_fouls = True
            self.break_at_zero = True
            self.lift_at_zero = True
            self.lift_3x = True
            self.first_shot_check = True
            self.wink_knock = True
            self.farewell_wills = True
            self.music = True
        return self


class RoomCreateIn(BaseModel):
    title: Title = Field(min_length=1, max_length=32)
    user_limit: Optional[int] = Field(default=None, ge=2, le=20)
    privacy: Literal["open", "private"] = Field(default="open")
    anonymity: Literal["visible", "hidden"] = Field(default="visible")
    game: Optional[GameParams] = Field(default_factory=GameParams)


class RoomIdOut(BaseModel):
    id: int


class RoomInfoMemberOut(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    profile_role: Optional[str] = None
    streaming_url: Optional[str] = None
    screen: Optional[bool] = None
    role: Optional[Literal["head", "player", "observer"]] = None
    slot: Optional[int] = None
    alive: Optional[bool] = None


class RoomInfoOut(BaseModel):
    members: List[RoomInfoMemberOut] = Field(default_factory=list)
    game: Optional[GameParams] = None
    spectators_count: int = 0


class RoomSpectatorOut(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    profile_role: Optional[str] = None


class RoomSpectatorsOut(BaseModel):
    spectators: List[RoomSpectatorOut] = Field(default_factory=list)


class RoomAccessOut(BaseModel):
    access: Literal["approved", "pending", "none", "blacklisted", "hidden"]


class RoomRequestOut(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    role: str
    theme_color: Optional[str] = None
    theme_icon: Optional[str] = None
    status: Literal["approved", "pending"]
    requested_at: Optional[datetime] = None


class RoomBriefOut(BaseModel):
    id: int
    title: str
    user_limit: int
    privacy: Literal["open", "private"]
    anonymity: Literal["visible", "hidden"] = Field(default="visible")
    creator: int
    creator_name: str
    creator_avatar_name: Optional[str] = None
    created_at: str
    occupancy: int
    in_game: bool
    game_phase: str
    entry_closed: bool
