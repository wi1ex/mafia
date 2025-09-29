from __future__ import annotations
import io
import mimetypes
from datetime import timedelta
from typing import Optional
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


async def download_telegram_photo(url: str) -> tuple[bytes, str] | None:
    try:
        client = get_httpx()
        async with client.stream("GET", url) as r:
            r.raise_for_status()
            cl = r.headers.get("content-length")
            if cl and cl.isdigit() and int(cl) > _MAX_BYTES:
                log.warning("telegram.photo.too_large.header", size=int(cl))
                return None

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
        ct_hdr = (r.headers.get("content-type") or "image/jpeg").split(";")[0].strip().lower()
        ct = ct_hdr if ct_hdr in _ct2ext else (_sniff_ct(data) or "image/jpeg")
        return data, ct

    except Exception as e:
        log.warning("telegram.photo.download_failed", err=type(e).__name__)
        return None


def put_avatar(user_id: int, content: bytes, content_type: str | None) -> Optional[str]:
    if len(content) > _MAX_BYTES:
        log.warning("avatar.too_large", user_id=user_id, bytes=len(content))
        return None

    ct_hdr = (content_type or "").split(";")[0].strip().lower()
    ct = ct_hdr if ct_hdr in _ct2ext else _sniff_ct(content)
    if ct not in _ct2ext:
        log.warning("avatar.unsupported_content_type", user_id=user_id, content_type=ct or content_type)
        return None

    minio = get_minio_private()
    ensure_bucket(minio)
    ext = _ct2ext[ct]
    prefix = f"avatars/{user_id}."
    to_delete = [DeleteObject(o.object_name) for o in minio.list_objects(_bucket, prefix=prefix, recursive=True)]
    if to_delete:
        errs = []
        for err in minio.remove_objects(_bucket, to_delete):
            errs.append({"object": getattr(err, "name", None), "code": getattr(err, "code", None)})
        if errs:
            log.warning("avatar.remove_old_errors", user_id=user_id, errors=errs)

    name, obj = f"{user_id}{ext}", f"avatars/{user_id}{ext}"
    minio.put_object(_bucket, obj, io.BytesIO(content), length=len(content), content_type=ct or mimetypes.types_map.get(ext, "image/jpeg"))
    log.info("avatar.stored", user_id=user_id, ext=ext, bytes=len(content))
    return name


def presign_avatar(filename: Optional[str], *, expires_hours: int = 1) -> Optional[str]:
    if not filename:
        return None

    try:
        minio = get_minio_public()
        url = minio.presigned_get_object(_bucket, f"avatars/{filename}", expires=timedelta(hours=expires_hours))
        return url

    except Exception:
        log.info("avatar.presign_failed")
        return None
