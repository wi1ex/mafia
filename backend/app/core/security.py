from __future__ import annotations
import hashlib
import hmac
import time
import uuid
import jwt
from typing import Any
from ..settings import settings


def _encode(kind: str, *, sub: int | str, sid: str, exp_s: int, extra: dict[str, Any] | None = None) -> str:
    iat = int(time.time())
    payload = {
        "typ": kind,
        "sub": str(sub),
        "sid": sid,
        "iat": iat,
        "exp": iat + exp_s,
        "iss": settings.DOMAIN,
        "aud": settings.DOMAIN,
    }
    if extra: payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


def create_access_token(*, sub: int | str, role: str, sid: str, ttl_minutes: int) -> str:
    return _encode("access", sub=sub, sid=sid, exp_s=ttl_minutes * 60, extra={"role": role})


def create_refresh_token(*, sub: int | str, sid: str, ttl_days: int) -> tuple[str, str]:
    jti = uuid.uuid4().hex
    return _encode("refresh", sub=sub, sid=sid, exp_s=ttl_days * 86400, extra={"jti": jti}), jti


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"], audience=settings.DOMAIN, issuer=settings.DOMAIN)


def verify_telegram_auth(data: dict[str, Any]) -> bool:
    h, ad = data.get("hash"), data.get("auth_date")
    if not h or not ad: return False
    check = "\n".join(f"{k}={data[k]}" for k in sorted(k for k in data if k != "hash"))
    secret = hashlib.sha256(settings.TG_BOT_TOKEN.encode()).digest()
    if not hmac.compare_digest(hmac.new(secret, check.encode(), hashlib.sha256).hexdigest(), h): return False
    try: return int(time.time()) - int(ad) <= 300
    except Exception: return False
