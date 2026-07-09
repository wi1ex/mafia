from __future__ import annotations
from pydantic import BaseModel


class KassaPaymentLinkCreateIn(BaseModel):
    email: str = ""
    plan: str = "month"
    currency: str = "RUB"
    payment_provider: str = ""
    payment_method: str = ""
    promo_code: str = ""


class KassaPaymentLinkCreateOut(BaseModel):
    payment_url: str
    contract_id: str | None = None
    processed: bool = False
