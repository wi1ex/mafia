from __future__ import annotations
import asyncio
import io
import json
import math
import re
import subprocess
from collections.abc import Iterable
from contextlib import suppress
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import structlog
from fastapi import HTTPException
from PIL import Image
from ..core.clients import get_minio_private, get_redis
from ..core.settings import settings
from .minio import delete_object, ensure_bucket

GIFT_MEDIA_PREFIX = "gifts/catalog/"
MAX_GIFT_BYTES = 2 * 1024 * 1024
MAX_GIFT_SIDE = 512
MAX_GIFT_SECONDS = 6
MAX_GIFT_FPS = 30
MAX_GIFT_FRAMES = MAX_GIFT_SECONDS * MAX_GIFT_FPS
PREVIEW_SIDE = 160
_HEVC_START = re.compile(rb"\x00\x00\x00?\x01")
_upload_cleanups: set[asyncio.Task[None]] = set()
log = structlog.get_logger()


def _preview_png(image: Image.Image) -> bytes:
    image.thumbnail((PREVIEW_SIDE, PREVIEW_SIDE), Image.Resampling.LANCZOS)
    result = io.BytesIO()
    image.save(result, format="PNG")
    return result.getvalue()


def _webp_preview(data: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(data), formats=["WEBP"]) as animation:
            if max(animation.size) > MAX_GIFT_SIDE or not 2 <= animation.n_frames <= MAX_GIFT_FRAMES:
                raise ValueError("webp dimensions or frames")

            duration = 0
            preview = None
            for index in range(animation.n_frames):
                animation.seek(index)
                frame = animation.convert("RGBA")
                frame_duration = int(animation.info.get("duration", 0))
                if frame_duration <= 0:
                    raise ValueError("webp frame duration")

                duration += frame_duration
                if duration > MAX_GIFT_SECONDS * 1000:
                    raise ValueError("webp duration")

                if preview is None:
                    low, high = frame.getchannel("A").getextrema()
                    if low < 255 and high > 0:
                        preview = _preview_png(frame)
            if preview is None or (duration + 1) * MAX_GIFT_FPS < animation.n_frames * 1000:
                raise ValueError("webp transparency or frame rate")

            return preview

    except (OSError, EOFError, ValueError, RuntimeError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, detail="gift_webp_invalid") from exc


def _ebml_vint(data: bytes, offset: int) -> tuple[int, int]:
    first = data[offset]
    size = 9 - first.bit_length()
    if not 1 <= size <= 8 or offset + size > len(data):
        raise ValueError("invalid EBML integer")

    return size, int.from_bytes(data[offset:offset + size], "big") & ((1 << (size * 7)) - 1)


def _is_webm(data: bytes) -> bool:
    if not data.startswith(b"\x1a\x45\xdf\xa3"):
        return False

    try:
        size, length = _ebml_vint(data, 4)
        offset = 4 + size
        end = offset + length
        if end > min(len(data), 4096):
            return False

        while offset < end:
            size, _ = _ebml_vint(data, offset)
            element = data[offset:offset + size]
            offset += size
            size, length = _ebml_vint(data, offset)
            offset += size
            if offset + length > end:
                return False

            if element == b"\x42\x82":
                return data[offset:offset + length] == b"webm"

            offset += length
    except (IndexError, ValueError):
        return False

    return False


def _run_media_tool(command: list[str], error: str) -> bytes:
    try:
        result = subprocess.run(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=12, check=True,
        )
    except FileNotFoundError as exc:
        raise HTTPException(503, detail="gift_video_tool_unavailable") from exc

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(422, detail=error) from exc

    return result.stdout


def _video_metadata(path: Path, *, webm: bool) -> tuple[int, int, str, str]:
    error = "gift_webm_invalid" if webm else "gift_hevc_invalid"
    command = [
        "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-max_alloc", "67108864",
        "-f", "matroska" if webm else "mov", "-show_entries",
        "stream=codec_type,codec_name,codec_tag_string,width,height,pix_fmt,avg_frame_rate,r_frame_rate"
        ":format=duration:format_tags=major_brand", "-of", "json", str(path),
    ]
    output = _run_media_tool(command, error)
    try:
        info = json.loads(output)
        stream, = info["streams"]
        if stream["codec_type"] != "video" or stream["codec_name"] != ("vp9" if webm else "hevc"):
            raise ValueError("video codec or extra tracks")

        if not webm and stream["codec_tag_string"] != "hvc1":
            raise ValueError("Apple HEVC requires hvc1")

        width, height = int(stream["width"]), int(stream["height"])
        duration = float(info["format"]["duration"])
        rate = stream.get("avg_frame_rate")
        fps = Fraction(rate if rate and rate != "0/0" else stream["r_frame_rate"])
        if min(width, height) < 1 or max(width, height) > MAX_GIFT_SIDE:
            raise ValueError("video dimensions")

        if not math.isfinite(duration) or not 0 < duration <= MAX_GIFT_SECONDS or not 0 < fps <= MAX_GIFT_FPS:
            raise ValueError("video duration or frame rate")

        brand = str(info["format"].get("tags", {}).get("major_brand", "")).strip()
        if not webm and not (brand.startswith("iso") or brand in {"qt", "mp41", "mp42", "M4V", "hvc1"}):
            raise ValueError("video container")

        return width, height, str(stream.get("pix_fmt") or ""), brand

    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise HTTPException(422, detail=error) from exc


def _video_preview(path: Path, width: int, height: int, *, webm: bool) -> bytes | None:
    error = "gift_webm_invalid" if webm else "gift_hevc_invalid"
    scale = min(1, PREVIEW_SIDE / max(width, height))
    width, height = max(1, round(width * scale)), max(1, round(height * scale))
    command = [
        "ffmpeg", "-v", "error", "-xerror", "-nostdin", "-filter_threads", "1",
        "-protocol_whitelist", "file,pipe", "-max_alloc", "67108864", "-threads", "1",
        "-max_pixels", str(MAX_GIFT_SIDE ** 2), "-c:v", "libvpx-vp9" if webm else "hevc",
        "-f", "matroska" if webm else "mov", "-i", str(path), "-map", "0:v:0",
        "-vf", f"scale={width}:{height}:flags=area,format=rgba", "-fps_mode", "passthrough",
        "-frames:v", str(MAX_GIFT_FRAMES + 1), "-pix_fmt", "rgba", "-threads:v", "1", "-f", "rawvideo", "pipe:1",
    ]
    data = _run_media_tool(command, error)
    frame_size = width * height * 4
    if len(data) % frame_size or not 2 <= len(data) // frame_size <= MAX_GIFT_FRAMES:
        raise HTTPException(422, detail=error)

    for offset in range(0, len(data), frame_size):
        alpha = data[offset + 3:offset + frame_size:4]
        if min(alpha) < 255 and max(alpha) > 0:
            frame = Image.frombytes("RGBA", (width, height), data[offset:offset + frame_size])
            return _preview_png(frame)

    return None


def _sei_has_alpha(data: bytes) -> bool:
    data = data.replace(b"\x00\x00\x03", b"\x00\x00")
    offset = 0
    try:
        while offset + 1 < len(data):
            payload_type = 0
            while data[offset] == 255:
                payload_type += 255
                offset += 1
            payload_type += data[offset]
            offset += 1
            length = 0
            while data[offset] == 255:
                length += 255
                offset += 1
            length += data[offset]
            offset += 1
            if offset + length > len(data):
                return False

            if payload_type == 165 and length >= 4 and data[offset] < 128:
                return True

            offset += length
    except IndexError:
        return False

    return False


def _validate_hevc_alpha(path: Path) -> None:
    data = _run_media_tool([
        "ffmpeg", "-v", "error", "-xerror", "-nostdin", "-protocol_whitelist", "file,pipe",
        "-max_alloc", "67108864", "-f", "mov", "-i", str(path), "-map", "0:v:0", "-c:v", "copy",
        "-bsf:v", "hevc_mp4toannexb", "-frames:v", str(MAX_GIFT_FRAMES + 1),
        "-fs", str(3 * MAX_GIFT_BYTES), "-f", "hevc", "pipe:1",
    ], "gift_hevc_invalid")
    layers = set()
    alpha_sei = False
    positions = iter(_HEVC_START.finditer(data))
    start = next(positions, None)
    while start is not None:
        end = next(positions, None)
        nal = data[start.end():end.start() if end else len(data)]
        start = end
        if len(nal) < 3:
            continue
        nal_type = (nal[0] >> 1) & 63
        if nal_type < 32:
            layers.add(((nal[0] & 1) << 5) | (nal[1] >> 3))
        elif nal_type in (39, 40) and not alpha_sei:
            alpha_sei = _sei_has_alpha(nal[2:].rstrip(b"\x00"))
    if not alpha_sei or 0 not in layers or len(layers) != 2:
        raise HTTPException(422, detail="gift_hevc_invalid")


def _prepare_assets(webp: bytes | None, webm: bytes | None, hevc: bytes | None) -> dict[str, tuple[str, str, bytes]]:
    if webp is not None:
        return {"webp_key": ("animation.webp", "image/webp", webp),
                "preview_key": ("preview.png", "image/png", _webp_preview(webp))}

    if webm is None or hevc is None or not _is_webm(webm):
        raise HTTPException(422, detail="gift_webm_invalid")

    with TemporaryDirectory(prefix="gift-media-") as temp_dir:
        webm_path = Path(temp_dir) / "upload.webm"
        hevc_path = Path(temp_dir) / "upload.mov"
        webm_path.write_bytes(webm)
        hevc_path.write_bytes(hevc)
        width, height, _, _ = _video_metadata(webm_path, webm=True)
        preview = _video_preview(webm_path, width, height, webm=True)
        if preview is None:
            raise HTTPException(422, detail="gift_webm_invalid")

        width, height, pixel_format, brand = _video_metadata(hevc_path, webm=False)
        _validate_hevc_alpha(hevc_path)
        hevc_preview = _video_preview(hevc_path, width, height, webm=False)
        if pixel_format.startswith("yuva") and hevc_preview is None:
            raise HTTPException(422, detail="gift_hevc_invalid")

    hevc_file = ("animation.mov", "video/quicktime") if brand == "qt" else ("animation.mp4", "video/mp4")
    return {"webm_key": ("animation.webm", "video/webm", webm),
            "hevc_key": (*hevc_file, hevc), "preview_key": ("preview.png", "image/png", preview)}


def _store_gift_media(webp: bytes | None, webm: bytes | None, hevc: bytes | None) -> dict[str, str]:
    assets = _prepare_assets(webp, webm, hevc)
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


async def store_gift_media(*, webp: bytes | None, webm: bytes | None, hevc: bytes | None) -> dict[str, str]:
    task = asyncio.create_task(asyncio.to_thread(_store_gift_media, webp, webm, hevc))
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
