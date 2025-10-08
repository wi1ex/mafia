from __future__ import annotations
import io
import mimetypes
import time
from datetime import timedelta
from typing import Optional, Tuple
import structlog
from minio import Minio
from minio.error import S3Error
from minio.deleteobjects import DeleteObject
from ..settings import settings
from ..core.clients import get_minio_private, get_minio_public, get_httpx

log = structlog.get_logger()

_bucket = settings.MINIO_BUCKET
_ct2ext = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
_MAX_BYTES = 5 * 1024 * 1024


def ensure_bucket(minio_client: Optional[Minio] = None) -> None:
    minio = minio_client or get_minio_private()
    if not minio.bucket_exists(_bucket):
        try:
            minio.make_bucket(_bucket)
            log.info("minio.bucket.created", bucket=_bucket)
        except S3Error as e:
            if e.code not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                log.exception("minio.bucket.create_failed", bucket=_bucket, code=e.code)
                raise


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


async def download_telegram_photo(url: str) -> Tuple[bytes, str] | None:
    try:
        client = get_httpx()
        async with client.stream("GET", url, follow_redirects=False, headers={"Accept": "image/*"}) as r:
            r.raise_for_status()
            cl = r.headers.get("content-length")
            if cl and cl.isdigit() and int(cl) > _MAX_BYTES:
                log.warning("telegram.photo.too_large.header", size=int(cl), url_host=r.url.host)
                return None

            ct_from_hdr = (r.headers.get("content-type") or "").split(";")[0].strip().lower() or None
            chunks: list[bytes] = []
            total = 0
            async for chunk in r.aiter_bytes():
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_BYTES:
                    log.warning("telegram.photo.too_large.stream", read_bytes=total)
                    return None

                chunks.append(chunk)

        data = b"".join(chunks)
        ct_guess = _sniff_ct(data)
        ct = ct_from_hdr if (ct_from_hdr in _ct2ext) else (ct_guess or "image/jpeg")
        return data, ct

    except Exception as e:
        log.error("telegram.photo.download_failed", err=type(e).__name__)
        return None


def put_avatar(user_id: int, content: bytes, content_type: str | None) -> Optional[str]:
    if len(content) > _MAX_BYTES:
        log.warning("avatar.put.too_large", user_id=user_id, bytes=len(content))
        return None

    ct_hdr = (content_type or "").split(";")[0].strip().lower()
    ct = ct_hdr if ct_hdr in _ct2ext else _sniff_ct(content)
    if ct not in _ct2ext:
        log.warning("avatar.put.unsupported_type", user_id=user_id, content_type=ct or content_type)
        return None

    minio = get_minio_private()
    ensure_bucket(minio)
    ext = _ct2ext[ct]
    name = f"{user_id}-{int(time.time())}{ext}"
    obj = f"avatars/{name}"
    prefix = f"avatars/{user_id}-"
    to_delete = [DeleteObject(o.object_name) for o in minio.list_objects(_bucket, prefix=prefix, recursive=True)]
    if to_delete:
        errs = []
        for err in minio.remove_objects(_bucket, to_delete):
            errs.append({"object": getattr(err, "name", None), "code": getattr(err, "code", None)})
        if errs:
            log.warning("avatar.remove_old_errors", user_id=user_id, errors=errs)

    try:
        minio.put_object(_bucket, obj, io.BytesIO(content), length=len(content), content_type=ct or mimetypes.types_map.get(ext, "image/jpeg"))
        return name

    except S3Error as e:
        log.error("avatar.put.s3_error", code=e.code, user_id=user_id)
        raise

    except Exception:
        log.exception("avatar.put.unexpected", user_id=user_id)
        raise


def presign_key(key: str, *, expires_hours: int = 1) -> tuple[str, int]:
    minio_pub = get_minio_public()
    minio_priv = get_minio_private()
    try:
        minio_priv.stat_object(_bucket, key)
    except S3Error as e:
        if e.code == "NoSuchKey":
            log.warning("media.presign.not_found", key=key)
            raise FileNotFoundError(key)

        log.error("media.presign.stat_failed", code=e.code, key=key)
        raise

    try:
        url = minio_pub.presigned_get_object(_bucket, key, expires=timedelta(hours=expires_hours))
        return url, int(expires_hours * 3600)

    except S3Error as e:
        log.error("media.presign.s3_error", code=e.code, key=key)
        raise

    except Exception:
        log.exception("media.presign.unexpected", key=key)
        raise
