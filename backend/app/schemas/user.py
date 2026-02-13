import unicodedata
from datetime import datetime
from typing import Any, Optional, List, Literal
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
    telegram_verified: bool = False
    password_temp: bool = False
    protected_user: bool = False
    hotkeys_visible: bool = True
    tg_invites_enabled: bool = True
    timeout_until: Optional[datetime] = None
    suspend_until: Optional[datetime] = None
    ban_active: bool = False


class UserSanctionOut(BaseModel):
    id: int
    kind: Literal["timeout", "ban", "suspend"]
    reason: Optional[str] = None
    issued_at: datetime
    issued_by_id: Optional[int] = None
    issued_by_name: Optional[str] = None
    duration_seconds: Optional[int] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by_id: Optional[int] = None
    revoked_by_name: Optional[str] = None


class UserSanctionsOut(BaseModel):
    items: List[UserSanctionOut]


class UsernameUpdateIn(BaseModel):
    username: UsernameClean = Field(min_length=2, max_length=20)


class UsernameUpdateOut(BaseModel):
    username: str


class AvatarUploadOut(BaseModel):
    avatar_name: Optional[str] = None


class UserUiPrefsIn(BaseModel):
    hotkeys_visible: Optional[bool] = None
    tg_invites_enabled: Optional[bool] = None


class UserUiPrefsOut(BaseModel):
    hotkeys_visible: bool
    tg_invites_enabled: bool


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=8, max_length=32)
    new_password: str = Field(min_length=8, max_length=32)
