from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl, Field


class UserOut(BaseModel):
    id: uuid.UUID
    username: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[HttpUrl] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
