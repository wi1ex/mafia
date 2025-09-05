from __future__ import annotations
from pydantic import BaseModel, Field

class RoomCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    user_limit: int = Field(ge=2, le=32)
    is_private: bool = False

class RoomOut(BaseModel):
    id: int
    title: str
    user_limit: int
    is_private: bool
    created_by_user_id: int
    created_at: str
    updated_at: str
    occupancy: int = 0
