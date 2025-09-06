from __future__ import annotations
import io
import mimetypes
import httpx
import structlog
from minio import Minio
from minio.error import S3Error
from ..settings import settings
from datetime import timedelta

log = structlog.get_logger()

_pub = Minio(
    settings.DOMAIN,
    access_key=settings.MINIO_ROOT_USER,
    secret_key=settings.MINIO_ROOT_PASSWORD,
    secure=True,
    region="us-east-1",
)

def presign_avatar(filename: str, *, ttl_seconds: int = 86400) -> str:
    # объект лежит как media/avatars/<filename>, поэтому путь: bucket + object
    return _pub.presigned_get_object(
        _bucket,
        f"avatars/{filename}",
        expires=timedelta(seconds=ttl_seconds),
    )

_client = Minio(
    settings.MINIO_ENDPOINT,                 # minio:9000
    access_key=settings.MINIO_ROOT_USER,
    secret_key=settings.MINIO_ROOT_PASSWORD,
    secure=False,
)
_bucket = settings.MINIO_BUCKET

def _avatar_key(filename: str) -> str:
    # защита от path traversal
    name = filename.split("/")[-1]
    return f"avatars/{name}"

def _ext_from_ct(ct: str) -> str:
    ct = (ct or "image/jpeg").split(";", 1)[0].strip()
    if ct == "image/jpeg": return ".jpg"
    if ct == "image/png": return ".png"
    if ct == "image/webp": return ".webp"
    if ct == "image/gif": return ".gif"
    return mimetypes.guess_extension(ct) or ".jpg"

async def download_telegram_photo(url: str, timeout=8.0) -> tuple[bytes, str] | None:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.content, _ext_from_ct(r.headers.get("content-type"))
    except Exception as e:
        log.warn("avatar_download_failed", url=url, err=str(e))
        return None

async def ensure_bucket() -> None:
    # синхронные вызовы MinIO допустимо держать краткими
    if not _client.bucket_exists(_bucket):
        _client.make_bucket(_bucket)

async def put_avatar(user_id: int, content: bytes, ext: str) -> str:
    await ensure_bucket()
    # удалить старые расширения
    prefix = f"avatars/{user_id}."
    for obj in _client.list_objects(_bucket, prefix=prefix, recursive=True):
        try: _client.remove_object(_bucket, obj.object_name)
        except S3Error: pass
    name = f"{user_id}{ext}"
    _client.put_object(
        _bucket,
        _avatar_key(name),
        io.BytesIO(content),
        length=len(content),
        content_type=mimetypes.types_map.get(ext, "image/jpeg"),
    )
    return name

def stat_avatar(filename: str):
    return _client.stat_object(_bucket, _avatar_key(filename))

def open_avatar(filename: str):
    # возвращает HTTPResponse (нужно закрывать)
    return _client.get_object(_bucket, _avatar_key(filename))
