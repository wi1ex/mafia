from __future__ import annotations
from minio import Minio
from minio.error import S3Error
import io
import mimetypes
import httpx
from ..settings import settings
from ..core.logging import structlog  # если нет – замените на logging

log = structlog.get_logger()

_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ROOT_USER,
    secret_key=settings.MINIO_ROOT_PASSWORD,
    secure=False,
)
_bucket = settings.MINIO_BUCKET

async def ensure_bucket():
    found = _client.bucket_exists(_bucket)
    if not found:
        _client.make_bucket(_bucket)

def _ext_from_ct(ct: str) -> str:
    ct = (ct or "image/jpeg").split(";")[0].strip()
    if ct == "image/jpeg": return ".jpg"
    if ct == "image/png": return ".png"
    if ct == "image/webp": return ".webp"
    if ct == "image/gif": return ".gif"
    return mimetypes.guess_extension(ct) or ".jpg"

async def download_telegram_photo(url: str, timeout=8.0) -> tuple[bytes, str] | None:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0",
        }) as client:
            r = await client.get(url)
            r.raise_for_status()
            ct = r.headers.get("content-type", "image/jpeg")
            return r.content, _ext_from_ct(ct)
    except Exception as e:
        log.warning("avatar_download_failed", url=url, err=str(e))
        return None

async def put_avatar(user_id: int, content: bytes, ext: str) -> str:
    await ensure_bucket()
    prefix = f"avatars/{user_id}."
    for obj in _client.list_objects(_bucket, prefix=prefix, recursive=True):
        try:
            _client.remove_object(_bucket, obj.object_name)
        except S3Error:
            pass

    name = f"{user_id}{ext}"
    objname = f"avatars/{name}"
    _client.put_object(
        _bucket,
        objname,
        io.BytesIO(content),
        length=len(content),
        content_type=mimetypes.types_map.get(ext, "image/jpeg"),
    )
    return name

def get_avatar_object(filename: str):
    return _client.get_object(_bucket, f"avatars/{filename}")
