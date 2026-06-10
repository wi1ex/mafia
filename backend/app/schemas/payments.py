from __future__ import annotations
from pydantic import BaseModel


class LavaPaymentLinkCreateIn(BaseModel):
    email: str = ""
    plan: str = "month"
    currency: str = "RUB"
    buyer_language: str = "RU"
    payment_provider: str = ""
    payment_method: str = ""
    promo_code: str = ""


class LavaPaymentLinkCreateOut(BaseModel):
    payment_url: str
    contract_id: str | None = None
