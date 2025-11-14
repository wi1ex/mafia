from __future__ import annotations
import re
import time
from contextlib import suppress
from fastapi import APIRouter, HTTPException, Query
from ...core.clients import get_redis
from ...core.decorators import log_route
from ...services.storage_minio import presign_key

router = APIRouter()


@log_route("media.presign")
@router.get("/presign")
async def presign(key: str = Query(..., description="")) -> dict:
    ALLOWED_PREFIXES = ("avatars/",)
    KEY_RE = re.compile(r"^[a-zA-Z0-9._/-]{3,256}$")

    if not key or not KEY_RE.match(key):
        raise HTTPException(status_code=400, detail="bad_key")

    if not any(key.startswith(p) for p in ALLOWED_PREFIXES):
        raise HTTPException(status_code=403, detail="forbidden_prefix")

    if ".." in key or "//" in key or key.endswith("/"):
        raise HTTPException(status_code=400, detail="bad_key")

    r = get_redis()
    now = int(time.time())
    cache_key = f"presign:{key}"

    with suppress(Exception):
        cached = await r.get(cache_key)
        if cached:
            url, exp_s = cached.split("|", 1)
            exp = int(exp_s)
            if exp - now > 30:
                return {"url": url, "expires_in": exp - now}

    try:
        url, ttl = presign_key(key, expires_hours=1)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="not_found")

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(status_code=500, detail="internal")

    exp = now + ttl
    cache_ttl = max(30, min(ttl - 30, 1 * 3600))
    with suppress(Exception):
        await r.setex(cache_key, cache_ttl, f"{url}|{exp}")

    return {"url": url, "expires_in": ttl}
