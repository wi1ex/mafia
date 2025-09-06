from __future__ import annotations
from typing import Optional
from minio import Minio
from minio.error import S3Error
import io, mimetypes, asyncio, httpx
from datetime import timedelta
from ..settings import settings

# клиент для внутренних операций (заливка/удаление)
_private = Minio(
    settings.MINIO_ENDPOINT,               # напр. "minio:9000"
    access_key=settings.MINIO_ROOT_USER,
    secret_key=settings.MINIO_ROOT_PASSWORD,
    secure=False,
)
# клиент для вычисления presign с публичным хостом (через nginx)
_public = Minio(
    settings.DOMAIN,                  # напр. "s3.domain.tld" (без схемы)
    access_key=settings.MINIO_ROOT_USER,
    secret_key=settings.MINIO_ROOT_PASSWORD,
    secure=True,
    region="us-east-1",
)

_bucket = settings.MINIO_BUCKET

def ensure_bucket():
    if not _private.bucket_exists(_bucket):
        _private.make_bucket(_bucket)

def _ext_from_ct(ct: str) -> str:
    if ct == "image/jpeg": return ".jpg"
    if ct == "image/png":  return ".png"
    if ct == "image/webp": return ".webp"
    if ct == "image/gif":  return ".gif"
    return mimetypes.guess_extension(ct) or ".jpg"

async def download_telegram_photo(url: str, timeout=5.0) -> tuple[bytes, str] | None:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
            r.raise_for_status()
            ct = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            return r.content, _ext_from_ct(ct)
    except Exception:
        return None

def put_avatar(user_id: int, content: bytes, ext: str) -> str:
    ensure_bucket()
    # удалить старые варианты
    prefix = f"avatars/{user_id}."
    for obj in _private.list_objects(_bucket, prefix=prefix, recursive=True):
        try: _private.remove_object(_bucket, obj.object_name)
        except S3Error: pass
    name = f"{user_id}{ext}"
    objname = f"avatars/{name}"
    _private.put_object(
        _bucket, objname, io.BytesIO(content), length=len(content),
        content_type=mimetypes.types_map.get(ext, "image/jpeg"),
    )
    return name

def presign_avatar(filename: str, *, expires_hours: int = 6) -> Optional[str]:
    if not filename:
        return None
    objname = f"avatars/{filename}"
    try:
        url = _public.presigned_get_object(_bucket, objname, expires=timedelta(hours=expires_hours))
        return url
    except Exception:
        return None
