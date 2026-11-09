from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from .common import Ok


class NotifOut(BaseModel):
    id: int
    title: str
    text: Optional[str] = None
    date: datetime
    read: bool = False


class NotifsListOut(BaseModel):
    items: List[NotifOut]
    unread_count: int
    has_more: bool = False
    next_before_id: Optional[int] = None
    cleared_through_id: int = 0


class MarkReadIn(BaseModel):
    ids: List[int] = Field(default_factory=list)
    all_before_id: Optional[int] = None


class ClearNotifsOut(Ok):
    through_id: int
