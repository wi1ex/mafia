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
    last_visit_at: Optional[datetime] = None
    last_game_at: Optional[datetime] = None
    last_game_id: Optional[int] = None
    online: bool = False
    last_room_id: Optional[int] = None
    last_spectator_room_id: Optional[int] = None
    timeouts_count: int
    bans_count: int
    suspends_count: int


class ModerationUsersOut(BaseModel):
    total: int
    items: List[ModerationUserOut] = Field(default_factory=list)
