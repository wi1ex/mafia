from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CoinPaymentAttemptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: int = Field(strict=True)
    currency: Literal["RUB", "USD", "EUR"]
    payment_method: Literal["card", "sbp", "apple_pay", "paypal"] = "card"

    @field_validator("quantity")
    @classmethod
    def fixed_package(cls, value: int) -> int:
        if value not in (30, 100, 300, 1000):
            raise ValueError("dc_package_invalid")

        return value


class CoinInvoiceCreateIn(CoinPaymentAttemptIn):
    email: str = Field(min_length=3, max_length=254)
    expected_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    request_id: UUID


class StoreOpenIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["header", "profile", "home_banner", "mini_profile_subscription", "mini_profile_gift"]


class CoinInvoiceOut(BaseModel):
    order_id: int
    status: str
    payment_url: str | None = None
    invoice_id: str | None = None
    dc_balance: int
    quantity: int
    unit_price: str | None = None
    amount: str | None = None
    currency: str | None = None
    email: str | None = None
    request_id: str | None = None
    error_code: str | None = None


class CoinInvoiceListOut(BaseModel):
    items: list[CoinInvoiceOut]


class SubscriptionPurchaseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: Literal["week", "month", "quarter", "year"]
    request_id: UUID
    recipient_id: int | None = Field(default=None, strict=True, gt=0, le=9223372036854775807)
    anonymous: bool = Field(default=False, strict=True)


class SubscriptionPurchaseOut(BaseModel):
    purchase_id: int
    dc_balance: int
    subscription_until: datetime
    subscription_active: bool = True
    recipient_id: int | None = None
    recipient_username: str | None = None
    anonymous: bool = False


class WalletOut(BaseModel):
    dc_balance: int
    subscription_active: bool
    subscription_until: datetime | None = None
