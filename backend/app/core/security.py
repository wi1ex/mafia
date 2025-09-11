from __future__ import annotations
import hashlib
import hmac
import time
from typing import Any
import jwt
from ..settings import settings


def _encode(kind: str, *, sub: int | str, exp_s: int, extra: dict[str, Any] | None = None) -> str:
    i = int(time.time())
    p = {
        "typ": kind,
        "sub": str(sub),
        "iat": i,
        "exp": i + exp_s,
    }
    if extra:
        p.update(extra)
    return jwt.encode(p, settings.JWT_SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])


def create_access_token(*, sub: int, role: str, ttl_minutes: int) -> str:
    return _encode("access", sub=sub, exp_s=ttl_minutes * 60, extra={"role": role})


def create_refresh_token(*, sub: int, ttl_days: int) -> str:
    return _encode("refresh", sub=sub, exp_s=ttl_days * 86400)


def verify_telegram_auth(data: dict[str, Any]) -> bool:
    h = data.get("hash")
    ad = data.get("auth_date")
    if not h or not ad:
        return False
    check = "\n".join(f"{k}={data[k]}" for k in sorted(k for k in data if k != "hash"))
    secret = hashlib.sha256(settings.TG_BOT_TOKEN.encode()).digest()
    if not hmac.compare_digest(hmac.new(secret, check.encode(), hashlib.sha256).hexdigest(), h):
        return False
    try:
        return int(time.time()) - int(ad) <= 300
    except Exception:
        return False
