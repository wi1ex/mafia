from typing import TypedDict
from pydantic import BaseModel, Field


class Ok(BaseModel):
    status: str = Field(default="ok")


class ErrorOut(BaseModel):
    detail: str


class Identity(TypedDict):
    id: int
    username: str
    role: str
