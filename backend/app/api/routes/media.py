from __future__ import annotations
import re
from fastapi import APIRouter, HTTPException, Query, status
from ...services.storage_minio import presign_key

router = APIRouter()

ALLOWED_PREFIXES = ("avatars/",)
KEY_RE = re.compile(r"^[a-zA-Z0-9._/-]{3,256}$")


@router.get("/presign")
async def presign(key: str = Query(..., description="avatars/123-1719050000.jpg")) -> dict:
    if not key or not KEY_RE.match(key):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_key")

    if not any(key.startswith(p) for p in ALLOWED_PREFIXES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden_prefix")

    try:
        url, ttl = presign_key(key, expires_hours=1)
        return {"url": url, "expires_in": ttl}

    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")

    except Exception:
        raise HTTPException(status_code=500, detail="internal")
