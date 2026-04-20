from __future__ import annotations
import asyncio
import io
import threading
import time
from urllib.parse import urlunsplit
from uuid import uuid4
from PIL import Image, ImageOps, ImageSequence
from datetime import datetime, timedelta, timezone
from typing import Optional
import structlog
from minio import Minio
from minio.datatypes import PostPolicy
from minio.error import S3Error
from minio.deleteobjects import DeleteObject
from ..core.settings import settings
from ..core.clients import get_minio_private, get_minio_public

log = structlog.get_logger()

_bucket = settings.MINIO_BUCKET
ALLOWED_CT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
}
AVATAR_ALLOWED_CT = {
    **ALLOWED_CT,
    "image/gif": ".gif",
}
MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 4096 * 4096
MAX_SIDE = 1024
MAX_AVATAR_GIF_FRAMES = 300
CHAT_IMAGE_MAX_BYTES = MAX_BYTES
CHAT_IMAGE_MAX_SIDE = MAX_SIDE
CHAT_IMAGE_PREFIX = "chat/global/images"
BUCKET_CHECK_TTL_S = 60.0
_bucket_checked_until = 0.0
_bucket_check_lock = threading.Lock()


def _normalize_content_type(content_type: str | None) -> str:
    return (content_type or "").split(";")[0].strip().lower()


def _reencode_safe(content: bytes, ct_hint: Optional[str], *, max_side: int = MAX_SIDE) -> tuple[bytes, str] | None:
    im = Image.open(io.BytesIO(content))
    im = ImageOps.exif_transpose(im)
    if im.width * im.height > MAX_PIXELS:
        return None

    im = im.convert("RGB")
    im.thumbnail((max_side, max_side), resample=Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    if (ct_hint or "").lower() == "image/png":
        im.save(buf, format="PNG", optimize=True)
        return buf.getvalue(), "image/png"

    im.save(buf, format="JPEG", quality=90, optimize=True)
    return buf.getvalue(), "image/jpeg"


def _make_static_preview(im: Image.Image, *, max_side: int = MAX_SIDE) -> bytes | None:
    frame = im.convert("RGBA")
    frame.thumbnail((max_side, max_side), resample=Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    frame.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _validate_gif_avatar(content: bytes, *, max_side: int = MAX_SIDE) -> tuple[bytes, str] | None:
    try:
        with Image.open(io.BytesIO(content)) as im:
            if str(getattr(im, "format", "") or "").upper() != "GIF":
                return None

            if im.width * im.height > MAX_PIXELS:
                return None

            if im.width > max_side or im.height > max_side:
                return None

            preview: bytes | None = None
            frame_seen = False
            for idx, frame in enumerate(ImageSequence.Iterator(im)):
                if idx >= MAX_AVATAR_GIF_FRAMES:
                    return None

                frame.load()
                if frame.width * frame.height > MAX_PIXELS:
                    return None

                if frame.width > max_side or frame.height > max_side:
                    return None

                if idx == 0:
                    preview = _make_static_preview(frame, max_side=max_side)
                frame_seen = True

            if not frame_seen or not preview:
                return None

            return preview, "image/png"

    except Exception:
        return None


def ensure_bucket(minio_client: Optional[Minio] = None) -> None:
    global _bucket_checked_until
    now = time.monotonic()
    if _bucket_checked_until > now:
        return

    with _bucket_check_lock:
        now = time.monotonic()
        if _bucket_checked_until > now:
            return

    minio = minio_client or get_minio_private()
    if not minio.bucket_exists(bucket_name=_bucket):
        try:
            minio.make_bucket(bucket_name=_bucket)
            log.info("minio.bucket.created", bucket=_bucket)
        except S3Error as e:
            if e.code not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                log.exception("minio.bucket.create_failed", bucket=_bucket, code=e.code)
                raise

    _bucket_checked_until = time.monotonic() + BUCKET_CHECK_TTL_S


def _sniff_ct(buf: bytes) -> Optional[str]:
    if buf.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    if buf.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    if buf.startswith(b"RIFF") and buf[8:12] == b"WEBP":
        return "image/webp"

    if buf.startswith(b"GIF8"):
        return "image/gif"

    return None


def put_avatar(user_id: int, content: bytes, content_type: str | None) -> Optional[str]:
    if not content:
        log.warning("avatar.put.empty", user_id=user_id)
        return None

    if len(content) > MAX_BYTES:
        log.warning("avatar.put.too_large", user_id=user_id, bytes=len(content))
        return None

    ct_hdr = (content_type or "").split(";")[0].strip().lower()
    ct_guess = _sniff_ct(content)
    ct = ct_hdr if ct_hdr in AVATAR_ALLOWED_CT else ct_guess
    if ct not in AVATAR_ALLOWED_CT:
        log.warning("avatar.put.unsupported_type", user_id=user_id, content_type=ct or content_type)
        return None

    preview_content: bytes | None = None
    preview_ct: str | None = None
    if ct == "image/gif":
        preview = _validate_gif_avatar(content, max_side=MAX_SIDE)
        if preview is None:
            return None

        preview_content, preview_ct = preview

    else:
        try:
            content, ct = _reencode_safe(content, ct, max_side=MAX_SIDE)
            if content is None or ct not in ALLOWED_CT:
                return None

        except Exception:
            log.warning("avatar.put.decode_failed", user_id=user_id)
            return None

    minio = get_minio_private()
    ensure_bucket(minio)
    ext = AVATAR_ALLOWED_CT[ct]
    name = f"{user_id}-{int(time.time())}{ext}"
    obj = f"avatars/{name}"
    preview_obj = f"avatars/{name[:-4]}.png" if ct == "image/gif" else None
    prefix = f"avatars/{user_id}-"
    to_delete = [DeleteObject(o.object_name) for o in minio.list_objects(bucket_name=_bucket, prefix=prefix, recursive=True)]
    if to_delete:
        errs = []
        for err in minio.remove_objects(bucket_name=_bucket, delete_object_list=to_delete):
            errs.append({"object": getattr(err, "name", None), "code": getattr(err, "code", None)})
        if errs:
            log.warning("avatar.remove_old_errors", user_id=user_id, errors=errs)

    try:
        minio.put_object(bucket_name=_bucket, object_name=obj, data=io.BytesIO(content), length=len(content), content_type=ct)
        if preview_obj and preview_content and preview_ct:
            minio.put_object(
                bucket_name=_bucket,
                object_name=preview_obj,
                data=io.BytesIO(preview_content),
                length=len(preview_content),
                content_type=preview_ct,
            )
        return name

    except S3Error as e:
        log.error("avatar.put.s3_error", code=e.code, user_id=user_id)
        raise

    except Exception:
        log.exception("avatar.put.unexpected", user_id=user_id)
        raise


def put_chat_image(user_id: int, content: bytes, content_type: str | None) -> Optional[str]:
    if not content:
        log.warning("chat_image.put.empty", user_id=user_id)
        return None

    if len(content) > CHAT_IMAGE_MAX_BYTES:
        log.warning("chat_image.put.too_large", user_id=user_id, bytes=len(content))
        return None

    ct_hdr = _normalize_content_type(content_type)
    ct_guess = _sniff_ct(content)
    ct = ct_hdr if ct_hdr in ALLOWED_CT else ct_guess
    if ct not in ALLOWED_CT:
        log.warning("chat_image.put.unsupported_type", user_id=user_id, content_type=ct or content_type)
        return None

    try:
        content, ct = _reencode_safe(content, ct, max_side=CHAT_IMAGE_MAX_SIDE)
        if content is None or ct not in ALLOWED_CT:
            return None

    except Exception:
        log.warning("chat_image.put.decode_failed", user_id=user_id)
        return None

    minio = get_minio_private()
    ensure_bucket(minio)
    ext = ALLOWED_CT[ct]
    object_name = f"{CHAT_IMAGE_PREFIX}/{int(user_id)}/{int(time.time())}-{uuid4().hex}{ext}"

    try:
        minio.put_object(
            bucket_name=_bucket,
            object_name=object_name,
            data=io.BytesIO(content),
            length=len(content),
            content_type=ct,
        )
        return object_name

    except S3Error as e:
        log.error("chat_image.put.s3_error", code=e.code, user_id=user_id)
        raise

    except Exception:
        log.exception("chat_image.put.unexpected", user_id=user_id)
        raise


def build_chat_image_object_name(user_id: int, content_type: str | None) -> str:
    ct = _normalize_content_type(content_type)
    ext = ALLOWED_CT.get(ct) or ".jpg"
    return f"{CHAT_IMAGE_PREFIX}/{int(user_id)}/{int(time.time())}-{uuid4().hex}{ext}"


def get_prefix_storage_stats(prefix: str) -> tuple[int, int]:
    minio = get_minio_private()
    ensure_bucket(minio)
    normalized_prefix = str(prefix or "").strip()
    if normalized_prefix and not normalized_prefix.endswith("/"):
        normalized_prefix += "/"

    count = 0
    total_bytes = 0
    try:
        for obj in minio.list_objects(bucket_name=_bucket, prefix=normalized_prefix, recursive=True):
            object_name = str(getattr(obj, "object_name", "") or "")
            if not object_name or object_name.endswith("/"):
                continue
            count += 1
            try:
                total_bytes += max(0, int(getattr(obj, "size", 0) or 0))
            except Exception:
                continue
    except S3Error as e:
        log.warning("minio.stats.list_failed", prefix=normalized_prefix, code=e.code)
        return 0, 0
    except Exception:
        log.exception("minio.stats.unexpected", prefix=normalized_prefix)
        return 0, 0

    return count, total_bytes


def _delete_object_quietly(minio_client: Minio, key: str) -> None:
    try:
        minio_client.remove_object(bucket_name=_bucket, object_name=key)
    except S3Error as e:
        if e.code not in {"NoSuchKey", "NoSuchObject"}:
            log.warning("chat_image.cleanup.s3_error", code=e.code, key=key)
    except Exception:
        log.warning("chat_image.cleanup.failed", key=key)


def _build_public_bucket_upload_url() -> str:
    return urlunsplit(("https", settings.DOMAIN, f"/{_bucket}", "", ""))


def _read_object_bytes(response) -> bytes:
    try:
        return response.read()

    finally:
        try:
            response.close()
        except Exception:
            pass
        try:
            response.release_conn()
        except Exception:
            pass


def build_chat_image_post_upload(key: str, content_type: str | None, *, expires_minutes: int = 15) -> tuple[str, dict[str, str], int]:
    ct = _normalize_content_type(content_type)
    if ct not in ALLOWED_CT:
        raise ValueError("unsupported_media_type")

    ensure_bucket()
    minio_pub = get_minio_public()
    policy = PostPolicy(_bucket, datetime.now(timezone.utc) + timedelta(minutes=expires_minutes))
    policy.add_equals_condition("key", key)
    policy.add_equals_condition("Content-Type", ct)
    policy.add_content_length_range_condition(1, CHAT_IMAGE_MAX_BYTES + 256 * 1024)
    form_data = dict(minio_pub.presigned_post_policy(policy))
    form_data["key"] = key
    form_data["Content-Type"] = ct
    upload_url = _build_public_bucket_upload_url()
    return upload_url, form_data, int(expires_minutes * 60)


def validate_chat_image_object(key: str) -> str:
    key_value = str(key or "").strip()
    if not key_value:
        raise ValueError("bad_image_key")

    minio = get_minio_private()
    ensure_bucket(minio)
    try:
        stat = minio.stat_object(bucket_name=_bucket, object_name=key_value)
    except S3Error as e:
        if e.code in {"NoSuchKey", "NoSuchObject"}:
            raise ValueError("image_not_found") from e

        raise

    size = int(getattr(stat, "size", 0) or 0)
    if size <= 0:
        _delete_object_quietly(minio, key_value)
        raise ValueError("empty_file")

    if size > CHAT_IMAGE_MAX_BYTES:
        _delete_object_quietly(minio, key_value)
        raise ValueError("file_too_large")

    response = minio.get_object(bucket_name=_bucket, object_name=key_value)
    data = _read_object_bytes(response)

    if not data:
        _delete_object_quietly(minio, key_value)
        raise ValueError("empty_file")

    if len(data) > CHAT_IMAGE_MAX_BYTES:
        _delete_object_quietly(minio, key_value)
        raise ValueError("file_too_large")

    ct_hdr = _normalize_content_type(getattr(stat, "content_type", None))
    ct_guess = _sniff_ct(data)
    ct = ct_guess if ct_guess in ALLOWED_CT else (ct_hdr if ct_hdr in ALLOWED_CT else None)
    if ct not in ALLOWED_CT:
        _delete_object_quietly(minio, key_value)
        raise ValueError("unsupported_media_type")

    try:
        normalized = _reencode_safe(data, ct, max_side=CHAT_IMAGE_MAX_SIDE)
    except Exception:
        normalized = None
    if normalized is None:
        _delete_object_quietly(minio, key_value)
        raise ValueError("bad_image")

    normalized_content, normalized_ct = normalized
    if not normalized_content or normalized_ct not in ALLOWED_CT:
        _delete_object_quietly(minio, key_value)
        raise ValueError("bad_image")

    if len(normalized_content) > CHAT_IMAGE_MAX_BYTES:
        _delete_object_quietly(minio, key_value)
        raise ValueError("file_too_large")

    if normalized_content != data or normalized_ct != ct_hdr:
        minio.put_object(
            bucket_name=_bucket,
            object_name=key_value,
            data=io.BytesIO(normalized_content),
            length=len(normalized_content),
            content_type=normalized_ct,
        )

    return key_value


def delete_avatars(user_id: int) -> int:
    minio = get_minio_private()
    ensure_bucket(minio)
    prefix = f"avatars/{user_id}-"

    to_delete = [DeleteObject(o.object_name) for o in minio.list_objects(bucket_name=_bucket, prefix=prefix, recursive=True)]
    if not to_delete:
        return 0

    errs = []
    for err in minio.remove_objects(bucket_name=_bucket, delete_object_list=to_delete):
        errs.append({"object": getattr(err, "name", None), "code": getattr(err, "code", None)})
    if errs:
        log.warning("avatar.remove.errors", user_id=user_id, errors=errs)
    return len(to_delete)


def delete_chat_images() -> int:
    minio = get_minio_private()
    ensure_bucket(minio)
    prefix = f"{CHAT_IMAGE_PREFIX}/"

    to_delete = [DeleteObject(o.object_name) for o in minio.list_objects(bucket_name=_bucket, prefix=prefix, recursive=True)]
    if not to_delete:
        return 0

    errs = []
    for err in minio.remove_objects(bucket_name=_bucket, delete_object_list=to_delete):
        errs.append({"object": getattr(err, "name", None), "code": getattr(err, "code", None)})
    if errs:
        log.warning("chat_image.remove.errors", errors=errs)
    return len(to_delete)


def presign_key(key: str, *, expires_hours: int = 1) -> tuple[str, int]:
    minio_pub = get_minio_public()
    minio_priv = get_minio_private()
    try:
        minio_priv.stat_object(bucket_name=_bucket, object_name=key)
    except S3Error as e:
        if e.code == "NoSuchKey":
            log.warning("media.presign.not_found", key=key)
            raise FileNotFoundError(key)

        log.error("media.presign.stat_failed", code=e.code, key=key)
        raise

    try:
        url = minio_pub.presigned_get_object(bucket_name=_bucket, object_name=key, expires=timedelta(hours=expires_hours))
        return url, int(expires_hours * 3600)

    except S3Error as e:
        log.error("media.presign.s3_error", code=e.code, key=key)
        raise

    except Exception:
        log.exception("media.presign.unexpected", key=key)
        raise


async def put_avatar_async(user_id: int, content: bytes, content_type: str | None) -> Optional[str]:
    return await asyncio.to_thread(put_avatar, user_id, content, content_type)


async def put_chat_image_async(user_id: int, content: bytes, content_type: str | None) -> Optional[str]:
    return await asyncio.to_thread(put_chat_image, user_id, content, content_type)


async def delete_avatars_async(user_id: int) -> int:
    return await asyncio.to_thread(delete_avatars, user_id)


async def delete_chat_images_async() -> int:
    return await asyncio.to_thread(delete_chat_images)


async def presign_key_async(key: str, *, expires_hours: int = 1) -> tuple[str, int]:
    return await asyncio.to_thread(presign_key, key, expires_hours=expires_hours)


async def build_chat_image_post_upload_async(key: str, content_type: str | None, *, expires_minutes: int = 15) -> tuple[str, dict[str, str], int]:
    return await asyncio.to_thread(build_chat_image_post_upload, key, content_type, expires_minutes=expires_minutes)


async def validate_chat_image_object_async(key: str) -> str:
    return await asyncio.to_thread(validate_chat_image_object, key)


async def get_prefix_storage_stats_async(prefix: str) -> tuple[int, int]:
    return await asyncio.to_thread(get_prefix_storage_stats, prefix)


def presign_put_key(key: str, *, expires_minutes: int = 15) -> tuple[str, int]:
    minio_pub = get_minio_public()
    try:
        url = minio_pub.presigned_put_object(bucket_name=_bucket, object_name=key, expires=timedelta(minutes=expires_minutes))
        return url, int(expires_minutes * 60)

    except S3Error as e:
        log.error("media.presign_put.s3_error", code=e.code, key=key)
        raise

    except Exception:
        log.exception("media.presign_put.unexpected", key=key)
        raise


async def presign_put_key_async(key: str, *, expires_minutes: int = 15) -> tuple[str, int]:
    return await asyncio.to_thread(presign_put_key, key, expires_minutes=expires_minutes)


def object_exists(key: str) -> bool:
    minio = get_minio_private()
    try:
        minio.stat_object(bucket_name=_bucket, object_name=key)
        return True

    except S3Error as e:
        if e.code in {"NoSuchKey", "NoSuchObject"}:
            return False

        raise


async def object_exists_async(key: str) -> bool:
    return await asyncio.to_thread(object_exists, key)


def delete_object(key: str) -> None:
    minio = get_minio_private()
    try:
        minio.remove_object(bucket_name=_bucket, object_name=key)
    except S3Error as e:
        if e.code in {"NoSuchKey", "NoSuchObject"}:
            return

        log.error("media.delete.s3_error", code=e.code, key=key)
        raise

    except Exception:
        log.exception("media.delete.unexpected", key=key)
        raise


async def delete_object_async(key: str) -> None:
    await asyncio.to_thread(delete_object, key)
