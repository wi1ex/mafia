from __future__ import annotations
from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse
from ...services.storage_minio import get_avatar_object
import mimetypes

router = APIRouter()

@router.get("/avatars/{filename}")
async def avatar(filename: str):
    try:
        obj = get_avatar_object(filename)
    except Exception:
        raise HTTPException(status_code=404, detail="not found")
    ext = "." + filename.split(".")[-1].lower()
    ct = mimetypes.types_map.get(ext, "image/jpeg")
    return StreamingResponse(
        obj.stream(32 * 1024),
        media_type=ct,
        headers={"Cache-Control": "public, max-age=3600"},
    )
