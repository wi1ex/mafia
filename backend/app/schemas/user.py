import unicodedata
from typing import Any, Optional
from pydantic import BaseModel, Field
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated

def _sanitize_username(v: Any) -> str:
    s = unicodedata.normalize("NFKC", str(v or ""))
    s = s.strip()
    return s

UsernameClean = Annotated[str, BeforeValidator(_sanitize_username)]


class UserOut(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    role: str


class UsernameUpdateIn(BaseModel):
    username: UsernameClean = Field(min_length=2, max_length=20)


class UsernameUpdateOut(BaseModel):
    username: str


class AvatarUploadOut(BaseModel):
    avatar_name: Optional[str] = None
