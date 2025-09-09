from __future__ import annotations
import time
import hmac
import hashlib
import uuid
from typing import Dict, Any
import jwt
from ..settings import settings

ALG = "HS256"


def _now() -> int: return int(time.time())


def create_access_token(*, sub: int | str, role: str, sid: str, ttl_minutes: int) -> str:
    iat = _now()
    payload = {"typ": "access",
               "sub": str(sub),
               "role": role,
               "sid": sid,
               "iat": iat,
               "exp": iat + ttl_minutes * 60,
               "iss": settings.DOMAIN,
               "aud": settings.DOMAIN}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALG)


def create_refresh_token(*, sub: int | str, sid: str, ttl_days: int) -> tuple[str, str]:
    iat = _now()
    jti = uuid.uuid4().hex
    payload = {"typ": "refresh",
               "sub": str(sub),
               "sid": sid,
               "jti": jti,
               "iat": iat,
               "exp": iat + ttl_days * 86400,
               "iss": settings.DOMAIN,
               "aud": settings.DOMAIN}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALG), jti


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALG], audience=settings.DOMAIN, issuer=settings.DOMAIN)


def verify_telegram_auth(data: Dict[str, Any]) -> bool:
    if "hash" not in data or "auth_date" not in data: return False
    received_hash = data["hash"]
    pairs = [f"{k}={data[k]}" for k in sorted(k for k in data.keys() if k != "hash")]
    check_string = "\n".join(pairs)
    secret_key = hashlib.sha256(settings.TG_BOT_TOKEN.encode()).digest()
    expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash): return False
    try:
        auth_date = int(data["auth_date"])
    except Exception:
        return False
    return _now() - auth_date <= 300
