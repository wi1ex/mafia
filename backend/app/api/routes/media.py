from __future__ import annotations
import time
from contextlib import suppress
from fastapi import APIRouter, HTTPException, Query
from ...core.clients import get_redis
from ...security.decorators import log_route
from ...services.minio import presign_key_async
from ..utils import validate_object_key_for_presign

router = APIRouter()


@log_route("media.presign")
@router.get("/presign")
async def presign(key: str = Query(..., description="")) -> dict:
    validate_object_key_for_presign(key)

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
        url, ttl = await presign_key_async(key, expires_hours=1)
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
