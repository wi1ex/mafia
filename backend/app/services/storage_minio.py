from __future__ import annotations
from typing import Optional
from minio.error import S3Error
import io
import mimetypes
from datetime import timedelta
from ..settings import settings
from ..core.clients import get_minio_private, get_minio_public, get_httpx

_bucket = settings.MINIO_BUCKET

def ensure_bucket():
    client = get_minio_private()
    if not client.bucket_exists(_bucket):
        client.make_bucket(_bucket)

def _ext_from_ct(ct: str) -> str:
    if ct == "image/jpeg": return ".jpg"
    if ct == "image/png": return ".png"
    if ct == "image/webp": return ".webp"
    if ct == "image/gif": return ".gif"
    return mimetypes.guess_extension(ct) or ".jpg"

async def download_telegram_photo(url: str) -> tuple[bytes, str] | None:
    try:
        client = get_httpx()
        r = await client.get(url)
        r.raise_for_status()
        ct = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        return r.content, _ext_from_ct(ct)
    except Exception:
        return None

def put_avatar(user_id: int, content: bytes, ext: str) -> str:
    priv = get_minio_private()
    ensure_bucket()
    prefix = f"avatars/{user_id}."
    for obj in priv.list_objects(_bucket, prefix=prefix, recursive=True):
        try: priv.remove_object(_bucket, obj.object_name)
        except S3Error: pass
    name = f"{user_id}{ext}"
    objname = f"avatars/{name}"
    priv.put_object(
        _bucket, objname, io.BytesIO(content), length=len(content),
        content_type=mimetypes.types_map.get(ext, "image/jpeg"),
    )
    return name

def presign_avatar(filename: str, *, expires_hours: int = 6) -> Optional[str]:
    if not filename:
        return None
    objname = f"avatars/{filename}"
    pub = get_minio_public()
    try:
        url = pub.presigned_get_object(_bucket, objname, expires=timedelta(hours=expires_hours))
        # Добавляем /media/ для nginx-прокси на том же домене
        host = f"https://{settings.DOMAIN}/"
        if url.startswith(host):
            url = url.replace(host, host + "media/", 1)
        return url
    except Exception:
        return None
