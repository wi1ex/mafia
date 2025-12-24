from datetime import date
from typing import List
from pydantic import BaseModel, Field


class UpdateOut(BaseModel):
    id: int
    version: str
    date: date
    description: str
    read: bool = False


class UpdatesListOut(BaseModel):
    items: List[UpdateOut]
    unread_count: int


class MarkUpdatesReadIn(BaseModel):
    ids: List[int] = Field(default_factory=list)
    all: bool = False


class AdminUpdateIn(BaseModel):
    version: str
    date: date
    description: str


class AdminUpdateOut(BaseModel):
    id: int
    version: str
    date: date
    description: str


class AdminUpdatesOut(BaseModel):
    items: List[AdminUpdateOut]
