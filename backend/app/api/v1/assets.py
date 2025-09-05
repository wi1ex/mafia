from __future__ import annotations
from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from ...services.storage_minio import get_avatar_object

router = APIRouter()

def _content_type(filename: str) -> str:
    f = filename.lower()
    if f.endswith(".png"): return "image/png"
    if f.endswith(".webp"): return "image/webp"
    if f.endswith(".gif"): return "image/gif"
    return "image/jpeg"

@router.get("/assets/avatars/{filename}")
async def serve_avatar(filename: str = Path(..., min_length=1, max_length=128)):
    try:
        obj = get_avatar_object(filename)   # MinIO Response
    except Exception:
        raise HTTPException(status_code=404, detail="not_found")

    # stream + корректное закрытие соединения
    return StreamingResponse(
        obj.stream(32 * 1024),
        media_type=_content_type(filename),
        headers={
            "Cache-Control": "public, max-age=86400, immutable",
            "Content-Disposition": f'inline; filename="{filename}"',
        },
        background=BackgroundTask(obj.close),
    )
