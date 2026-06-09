from __future__ import annotations
from pydantic import BaseModel


class LavaPaymentLinkCreateOut(BaseModel):
    payment_url: str
