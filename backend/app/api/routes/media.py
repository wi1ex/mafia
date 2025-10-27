from __future__ import annotations
import re
import time
from fastapi import APIRouter, HTTPException, Query, status
from ...core.decorators import log_route
from ...services.storage_minio import presign_key
from ...core.clients import get_redis

router = APIRouter()


@log_route("media.presign")
@router.get("/presign")
async def presign(key: str = Query(..., description="")) -> dict:
    if not key or not re.compile(r"^[a-zA-Z0-9._/-]{3,256}$").match(key):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_key")

    if not any(key.startswith(p) for p in ("avatars/",)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden_prefix")

    r = get_redis()
    now = int(time.time())
    cache_key = f"presign:{key}"

    try:
        cached = await r.get(cache_key)
        if cached:
            url, exp_s = cached.split("|", 1)
            exp = int(exp_s)
            if exp - now > 30:
                return {"url": url, "expires_in": exp - now}

    except Exception:
        pass

    try:
        url, ttl = presign_key(key, expires_hours=1)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(status_code=500, detail="internal")

    exp = now + ttl
    cache_ttl = max(30, min(ttl - 30, 1 * 3600))
    try:
        await r.setex(cache_key, cache_ttl, f"{url}|{exp}")
    except Exception:
        pass

    return {"url": url, "expires_in": ttl}
