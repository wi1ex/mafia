from __future__ import annotations
import hashlib
import hmac
import time
from typing import Any
import structlog
import jwt
from ..settings import settings


log = structlog.get_logger()


def _encode(kind: str, *, sub: int | str, exp_s: int, extra: dict[str, Any] | None = None) -> str:
    i = int(time.time())
    p = {"typ": kind, "sub": str(sub), "iat": i, "exp": i + exp_s}
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
        log.warning(
            "tg.verify.bad_hash",
            calc_prefix=calc[:12],
            got_prefix=str(h)[:12],
            check_preview=(check.decode("utf-8")[:200] + "...") if len(check) > 200 else check.decode("utf-8"),
            token_sha256_prefix=hashlib.sha256(settings.TG_BOT_TOKEN.encode()).hexdigest()[:12],
        )
        return False

    log.info("tg.verify.ok")
    return True
