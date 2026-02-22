from typing import Any, TypedDict
from pydantic import BaseModel, Field


class Ok(BaseModel):
    status: str = Field(default="ok")


class ErrorOut(BaseModel):
    detail: str | dict[str, Any]


class Identity(TypedDict):
    id: int
    username: str
    role: str
