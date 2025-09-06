from __future__ import annotations
from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from ...services.storage_minio import stat_avatar, open_avatar

router = APIRouter()

def _content_type(filename: str) -> str:
    f = filename.lower()
    if f.endswith(".png"): return "image/png"
    if f.endswith(".webp"): return "image/webp"
    if f.endswith(".gif"): return "image/gif"
    return "image/jpeg"

@router.get("/assets/avatars/{filename}")
async def serve_avatar(
    filename: str = Path(..., pattern=r"^[0-9A-Za-z._-]{1,128}$")
):
    # 1) есть ли объект
    try:
        await run_in_threadpool(stat_avatar, filename)
    except Exception:
        raise HTTPException(status_code=404, detail="not_found")

    # 2) поток
    obj = await run_in_threadpool(open_avatar, filename)

    async def _gen():
        try:
            for chunk in obj.stream(32 * 1024):
                yield chunk
        finally:
            try:
                obj.close()
                obj.release_conn()
            except Exception:
                pass

    return StreamingResponse(
        _gen(),
        media_type=_content_type(filename),
        headers={"Cache-Control": "public, max-age=86400, immutable",
                 "Content-Disposition": f'inline; filename="{filename}"'},
        background=BackgroundTask(lambda: None),  # закрываем сами в finally
    )
