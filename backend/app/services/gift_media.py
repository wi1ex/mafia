from __future__ import annotations
import asyncio
import io
from collections.abc import Iterable
from contextlib import suppress
from uuid import uuid4
import structlog
from fastapi import HTTPException
from PIL import Image
from ..core.clients import get_minio_private, get_redis
from ..core.settings import settings
from .minio import delete_object, ensure_bucket

GIFT_MEDIA_PREFIX = "gifts/catalog/"
MAX_GIFT_BYTES = 3 * 1024 * 1024
MAX_GIFT_SIDE = 1024
MAX_GIFT_SECONDS = 6
MAX_GIFT_FPS = 45
MAX_GIFT_FRAMES = MAX_GIFT_SECONDS * MAX_GIFT_FPS
PREVIEW_SIDE = 160
_upload_cleanups: set[asyncio.Task[None]] = set()
log = structlog.get_logger()


def _preview_png(image: Image.Image) -> bytes:
    image.thumbnail((PREVIEW_SIDE, PREVIEW_SIDE), Image.Resampling.LANCZOS)
    result = io.BytesIO()
    image.save(result, format="PNG")
    return result.getvalue()


def _avif_preview(data: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(data), formats=["AVIF"]) as animation:
            frame_count = getattr(animation, "n_frames", 1)
            if max(animation.size) > MAX_GIFT_SIDE or not 2 <= frame_count <= MAX_GIFT_FRAMES:
                raise ValueError("avif dimensions or frames")

            start_ms = duration_ms = 0
            preview = None
            for index in range(frame_count):
                animation.seek(index)
                animation.load()
                timestamp = animation.info["timestamp"]
                frame_duration = animation.info["duration"]
                if index == 0:
                    start_ms = timestamp

                # Pillow rounds timestamps and frame durations to milliseconds.
                duration_ms = timestamp + frame_duration - start_ms
                if frame_duration <= 0 or not 0 < duration_ms <= MAX_GIFT_SECONDS * 1000 + 1:
                    raise ValueError("avif duration")

                if preview is None and "A" in animation.getbands():
                    low, high = animation.getchannel("A").getextrema()
                    if low < 255 and high > 0:
                        preview = _preview_png(animation.copy())

            if preview is None or (duration_ms + 1) * MAX_GIFT_FPS < frame_count * 1000:
                raise ValueError("avif transparency or frame rate")

            return preview
    except (OSError, EOFError, KeyError, ValueError, RuntimeError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, detail="gift_avif_invalid") from exc


def _store_gift_media(avif: bytes) -> dict[str, str]:
    assets = {
        "avif_key": ("animation.avif", "image/avif", avif),
        "preview_key": ("preview.png", "image/png", _avif_preview(avif)),
    }
    prefix = f"{GIFT_MEDIA_PREFIX}{uuid4().hex}/"
    keys: dict[str, str] = {}
    try:
        minio = get_minio_private()
        ensure_bucket(minio)
        for field, (filename, content_type, content) in assets.items():
            key = prefix + filename
            keys[field] = key
            minio.put_object(bucket_name=settings.MINIO_BUCKET, object_name=key, data=io.BytesIO(content),
                             length=len(content), content_type=content_type)
    except Exception as exc:
        log.exception("gift.media_upload_failed")
        for key in keys.values():
            with suppress(Exception):
                delete_object(key)
        raise HTTPException(503, detail="gift_media_upload_failed") from exc
    return keys


async def store_gift_media(avif: bytes) -> dict[str, str]:
    task = asyncio.create_task(asyncio.to_thread(_store_gift_media, avif))
    try:
        return await asyncio.shield(task)

    except asyncio.CancelledError:
        async def cleanup() -> None:
            with suppress(Exception):
                keys = await task
                await delete_gift_media(keys.values())

        cleanup_task = asyncio.create_task(cleanup())
        _upload_cleanups.add(cleanup_task)
        cleanup_task.add_done_callback(_upload_cleanups.discard)
        await asyncio.shield(cleanup_task)
        raise


async def delete_gift_media(keys: Iterable[str | None]) -> bool:
    success = True
    for key in keys:
        if not key or not key.startswith(GIFT_MEDIA_PREFIX):
            continue
        try:
            await asyncio.to_thread(delete_object, key)
        except Exception:
            success = False
            log.exception("gift.media_delete_failed", key=key)
        with suppress(Exception):
            await get_redis().delete(f"presign:{key}")
    return success
