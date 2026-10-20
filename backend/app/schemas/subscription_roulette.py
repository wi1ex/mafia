from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class SubscriptionRouletteSpinIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    round_id: int | None = Field(default=None, strict=True, ge=0, le=9223372036854775807)


class SubscriptionRouletteNotificationOut(BaseModel):
    id: int
    title: str
    text: str
    date: datetime
    read: bool
    kind: Literal["subscription"] = "subscription"
    source: Literal["subscription_roulette"] = "subscription_roulette"
    ttl_ms: int = 15000


class SubscriptionRouletteStatusOut(BaseModel):
    round_id: int = Field(ge=0)
    enabled: bool
    verified: bool
    eligible: bool
    already_spun: bool
    subscription_roulette_days: int | None = Field(default=None, ge=1, le=30)
    subscription_until: datetime | None = None
    notification: SubscriptionRouletteNotificationOut | None = None


class SubscriptionRouletteSpinOut(SubscriptionRouletteStatusOut):
    subscription_roulette_days: int = Field(ge=1, le=30)
