from __future__ import annotations
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from ..models.gift import GIFT_PRICES
from .common import Ok


class GiftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    price_dc: int
    visible: bool
    preview_key: str
    avif_key: str


class GiftAdminOut(GiftOut):
    owner_count: int


class GiftOwnerOut(BaseModel):
    id: int
    username: str
    avatar_name: str | None
    quantity: int


class GiftOwnersOut(BaseModel):
    items: list[GiftOwnerOut]
    has_more: bool


class GiftAdminPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price_dc: int | None = Field(default=None, strict=True, gt=0, le=2**63 - 1)
    visible: bool | None = Field(default=None, strict=True)

    @field_validator("price_dc")
    @classmethod
    def validate_price(cls, value: int | None) -> int | None:
        if value is not None and value not in GIFT_PRICES:
            raise ValueError("gift_price_invalid")

        return value


class GiftPurchaseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gift_id: int = Field(strict=True, gt=0, le=2**31 - 1)
    expected_dc_cost: int = Field(strict=True, gt=0, le=2**63 - 1)
    request_id: UUID
    recipient_id: int | None = Field(default=None, strict=True, gt=0, le=2**63 - 1)
    anonymous: bool = Field(default=False, strict=True)


class GiftPurchaseOut(BaseModel):
    purchase_id: int
    gift_id: int
    recipient_id: int
    recipient_username: str
    dc_balance: int


class GiftMoveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acquisition_id: int = Field(strict=True, gt=0, le=2**31 - 1)
    target_id: int = Field(strict=True, gt=0, le=2**31 - 1)
    place: Literal["before", "after"]


class GiftSenderOut(BaseModel):
    id: int
    username: str
    avatar_name: str | None = None
    role: str | None = None
    theme_color: str | None = None
    theme_icon: str | None = None


class UserGiftOut(BaseModel):
    id: int
    gift_id: int
    quantity: int
    acquired_at: datetime
    preview_key: str
    avif_key: str
    sender: GiftSenderOut | None = None


class UserGiftsOut(BaseModel):
    items: list[UserGiftOut]
    total: int
    has_more: bool


class MyGiftOut(BaseModel):
    id: int
    gift_id: int
    acquired_at: datetime
    preview_key: str
    dc_cost: int
    payer_kind: Literal["self", "named", "anonymous"]
    sender: GiftSenderOut | None = None


class MyGiftsOut(BaseModel):
    items: list[MyGiftOut]
    total: int
    has_more: bool


class GiftRemovalOut(Ok):
    dc_balance: int


class GiftRemovalQuoteOut(BaseModel):
    cost_dc: int
    dc_balance: int
