from __future__ import annotations
import time, hmac, hashlib
from typing import Dict, Any
import jwt
from ..settings import settings

ALG = "HS256"

def create_access_token(*, sub: str, role: str, ttl_minutes: int) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "role": role,
        "iat": now,
        "exp": now + ttl_minutes * 60,
        "iss": settings.DOMAIN,
        "aud": settings.DOMAIN,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALG)

def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALG], audience=settings.DOMAIN, issuer=settings.DOMAIN)

def verify_telegram_auth(data: Dict[str, Any]) -> bool:
    if "hash" not in data or "auth_date" not in data:
        return False
    received_hash = data["hash"]
    pairs = [f"{k}={data[k]}" for k in sorted(k for k in data.keys() if k != "hash")]
    check_string = "\n".join(pairs)
    secret_key = hashlib.sha256(settings.TELEGRAM_BOT_TOKEN.encode()).digest()
    expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        return False
    try:
        auth_date = int(data["auth_date"])
    except Exception:
        return False
    return int(time.time()) - auth_date <= 86400
