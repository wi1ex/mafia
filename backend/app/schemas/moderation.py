from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from .admin import AdminSanctionOut


class ModerationUserOut(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    registered_at: datetime
    last_login_at: datetime
    last_visit_at: datetime
    last_game_at: Optional[datetime] = None
    timeout_active: bool
    timeout_until: Optional[datetime] = None
    suspend_active: bool
    suspend_until: Optional[datetime] = None
    timeouts_count: int
    bans_count: int
    suspends_count: int
    timeouts: List[AdminSanctionOut] = Field(default_factory=list)
    bans: List[AdminSanctionOut] = Field(default_factory=list)
    suspends: List[AdminSanctionOut] = Field(default_factory=list)


class ModerationUsersOut(BaseModel):
    total: int
    items: List[ModerationUserOut] = Field(default_factory=list)
