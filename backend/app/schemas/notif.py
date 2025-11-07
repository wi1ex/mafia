from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class NotifUser(BaseModel):
    id: int
    username: Optional[str] = None
    avatar_name: Optional[str] = None


class NotifAction(BaseModel):
    kind: Literal["api", "route"]
    label: str
    to: Optional[str] = None
    url: Optional[str] = None
    method: Optional[Literal["get", "post", "put", "delete"]] = "post"
    body: Optional[dict] = None


class NotifOut(BaseModel):
    id: int
    title: str
    text: Optional[str] = None
    date: datetime
    kind: Optional[str] = None
    room_id: Optional[int] = None
    user: Optional[NotifUser] = None
    action: Optional[NotifAction] = None
    read: bool = False
    ttl_ms: Optional[int] = None


class NotifsListOut(BaseModel):
    items: List[NotifOut]
    unread_count: int


class MarkReadIn(BaseModel):
    ids: List[int] = Field(default_factory=list)
    all_before_id: Optional[int] = None
