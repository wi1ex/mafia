from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class NotifOut(BaseModel):
    id: int
    title: str
    text: Optional[str] = None
    date: datetime
    read: bool = False


class NotifsListOut(BaseModel):
    items: List[NotifOut]
    unread_count: int


class MarkReadIn(BaseModel):
    ids: List[int] = Field(default_factory=list)
    all_before_id: Optional[int] = None
