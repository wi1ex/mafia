from __future__ import annotations
from pydantic import BaseModel


class LavaPaymentLinkCreateIn(BaseModel):
    email: str = ""
    plan: str = "month"


class LavaPaymentLinkCreateOut(BaseModel):
    payment_url: str
    contract_id: str | None = None
