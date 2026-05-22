from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ModerationUserOut(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None
    role: str
    registered_at: datetime
    last_room_id: Optional[int] = None
    last_spectator_room_id: Optional[int] = None
    timeout_active: bool
    timeout_until: Optional[datetime] = None
    suspend_active: bool
    suspend_until: Optional[datetime] = None
    timeouts_count: int
    bans_count: int
    suspends_count: int


class ModerationUsersOut(BaseModel):
    total: int
    items: List[ModerationUserOut] = Field(default_factory=list)
