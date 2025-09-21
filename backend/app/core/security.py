from __future__ import annotations
import hashlib
import hmac
import time
from typing import Any, Dict
import structlog
import jwt
from ..settings import settings

log = structlog.get_logger()


def _encode(kind: str, *, sub: int | str, exp_s: int, extra: Dict[str, Any] | None = None) -> str:
    i = int(time.time())
    p: Dict[str, Any] = {"typ": kind, "sub": str(sub), "iat": i, "exp": i + exp_s}
    if extra:
        p.update(extra)
    return jwt.encode(p, settings.JWT_SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])


def parse_refresh_token(raw: str) -> tuple[bool, int, str, str]:
    try:
        p = decode_token(raw)
        if p.get("typ") != "refresh":
            log.debug("jwt.bad_type", typ=p.get("typ"))
            return False, 0, "", ""
        uid = int(p.get("sub") or 0)
        sid = str(p.get("sid") or "")
        jti = str(p.get("jti") or "")
        if not uid or not sid or not jti:
            log.debug("jwt.missing_claims")
            return False, 0, "", ""
        return True, uid, sid, jti
    except Exception as e:
        log.debug("jwt.decode_failed", err=type(e).__name__)
        return False, 0, "", ""


def create_access_token(*, sub: int, role: str, ttl_minutes: int) -> str:
    return _encode("access", sub=sub, exp_s=ttl_minutes * 60, extra={"role": role})


def create_refresh_token(*, sub: int, sid: str, jti: str, ttl_days: int) -> str:
    return _encode("refresh", sub=sub, exp_s=ttl_days * 86400, extra={"sid": sid, "jti": jti})


def verify_telegram_auth(data: Dict[str, Any]) -> bool:
    h = data.get("hash")
    ad = data.get("auth_date")
    if not h or not ad:
        log.warning("tg.verify.missing_fields")
        return False

    try:
        if int(time.time()) - int(ad) > 12 * 3600:
            log.warning("tg.verify.expired")
            return False
    except Exception:
        log.warning("tg.verify.bad_auth_date", auth_date=ad)
        return False

    secret = hashlib.sha256(settings.TG_BOT_TOKEN.encode()).digest()
    check = "\n".join(f"{k}={data[k]}" for k in sorted(k for k in data.keys() if k != "hash")).encode()
    calc = hmac.new(secret, check, hashlib.sha256).hexdigest()

    ok = hmac.compare_digest(calc, h)
    if not ok:
        log.warning("tg.verify.bad_hash")
        return False

    log.info("tg.verify.ok")
    return True
