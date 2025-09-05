from __future__ import annotations
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from mimetypes import guess_type
from ...services.storage_minio import get_avatar_object

router = APIRouter()

@router.get("/avatars/{filename}")
async def get_avatar(filename: str):
    try:
        obj = get_avatar_object(filename)
    except Exception:
        raise HTTPException(status_code=404, detail="not found")
    ct, _ = guess_type(filename)
    return StreamingResponse(obj.stream(32 * 1024), media_type=ct or "image/jpeg")
