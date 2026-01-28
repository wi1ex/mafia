import re
import unicodedata
from typing_extensions import Annotated
from typing import Optional, List, Literal, Any
from pydantic.functional_validators import BeforeValidator
from pydantic import BaseModel, Field

_CTRL_RE = re.compile(r'[\x00-\x1F\x7F]')
_BIDI_RE = re.compile(r'[\u200B-\u200F\u202A-\u202E\u2066-\u2069]')
_WS_RE = re.compile(r'\s+')

def _sanitize_title(v: Any) -> str:
    s = unicodedata.normalize("NFKC", str(v or ""))
    s = _CTRL_RE.sub("", s)
    s = _BIDI_RE.sub("", s)
    s = _WS_RE.sub(" ", s).strip()
    return s

Title = Annotated[str, BeforeValidator(_sanitize_title)]


class GameParams(BaseModel):
    mode: Literal["normal", "rating"] = "normal"
    format: Literal["hosted", "nohost"] = "hosted"
    spectators_limit: int = Field(ge=0, le=10, default=0)
    nominate_mode: Literal["players", "head"] = "players"
    break_at_zero: bool = Field(default=True)
    lift_at_zero: bool = Field(default=True)
    lift_3x: bool = Field(default=True)
    wink_knock: bool = Field(default=True)
    farewell_wills: bool = Field(default=True)
    music: bool = Field(default=True)


class RoomCreateIn(BaseModel):
    title: Title = Field(min_length=1, max_length=32)
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
    role: Optional[Literal["head", "player", "observer"]] = None
    slot: Optional[int] = None
    alive: Optional[bool] = None


class RoomInfoOut(BaseModel):
    members: List[RoomInfoMemberOut] = Field(default_factory=list)
    game: Optional[GameParams] = None
    spectators_count: int = 0


class RoomAccessOut(BaseModel):
    access: Literal["approved", "pending", "none"]


class RoomRequestOut(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    role: str
    status: Literal["approved", "pending"]
