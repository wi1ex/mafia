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


async def download_telegram_photo(url: str) -> tuple[bytes, str] | None:
    try:
        r = await get_httpx().get(url)
        r.raise_for_status()
        content_type = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        return r.content, content_type
    except Exception as e:
        log.warning("telegram.photo.download_failed", err=type(e).__name__)
        return None


def put_avatar(user_id: int, content: bytes, content_type: str | None) -> Optional[str]:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct not in set(_ct2ext.keys()):
        log.warning("avatar.unsupported_content_type", user_id=user_id, content_type=ct or content_type)
        return None

    minio = get_minio_private()
    ensure_bucket(minio)
    ext = _ct2ext[ct]
    prefix = f"avatars/{user_id}."
    to_delete = [DeleteObject(o.object_name) for o in minio.list_objects(_bucket, prefix=prefix, recursive=True)]
    if to_delete:
        for err in minio.remove_objects(_bucket, to_delete):
            log.debug("avatar.remove_old_failed", user_id=user_id, object=getattr(err, "name", None), code=getattr(err, "code", None))

    name, obj = f"{user_id}{ext}", f"avatars/{user_id}{ext}"
    minio.put_object(_bucket, obj, io.BytesIO(content), length=len(content), content_type=ct or mimetypes.types_map.get(ext, "image/jpeg"))
    log.info("avatar.stored", user_id=user_id, ext=ext, bytes=len(content))
    return name


def presign_avatar(filename: str, *, expires_hours: int = 1) -> Optional[str]:
    if not filename:
        return None
    try:
        minio = get_minio_public()
        url = minio.presigned_get_object(_bucket, f"avatars/{filename}", expires=timedelta(hours=expires_hours))
        return url
    except Exception:
        log.debug("avatar.presign_failed")
        return None
