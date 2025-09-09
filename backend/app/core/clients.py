from __future__ import annotations
import httpx
import redis.asyncio as redis
from minio import Minio
from ..settings import settings

_redis: redis.Redis | None = None
_minio_private: Minio | None = None
_minio_public: Minio | None = None
_httpx: httpx.AsyncClient | None = None


def _build_redis() -> redis.Redis:
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
        decode_responses=True,
    )


def _build_minio_private() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ROOT_USER,
        secret_key=settings.MINIO_ROOT_PASSWORD,
        secure=False,
    )


def _build_minio_public() -> Minio:
    return Minio(
        settings.DOMAIN,
        access_key=settings.MINIO_ROOT_USER,
        secret_key=settings.MINIO_ROOT_PASSWORD,
        secure=True,
        region="us-east-1",
    )


def _build_httpx() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(5.0),
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        http2=True,
    )


def init_clients() -> None:
    global _redis, _minio_private, _minio_public, _httpx
    _redis = _redis or _build_redis()
    _minio_private = _minio_private or _build_minio_private()
    _minio_public = _minio_public or _build_minio_public()
    _httpx = _httpx or _build_httpx()


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        init_clients()
    if _redis is None:
        raise RuntimeError("Redis client not initialized")
    return _redis


def get_minio_private() -> Minio:
    global _minio_private
    if _minio_private is None:
        init_clients()
    if _minio_private is None:
        raise RuntimeError("MinIO (private) client not initialized")
    return _minio_private


def get_minio_public() -> Minio:
    global _minio_public
    if _minio_public is None:
        init_clients()
    if _minio_public is None:
        raise RuntimeError("MinIO (public) client not initialized")
    return _minio_public


def get_httpx() -> httpx.AsyncClient:
    global _httpx
    if _httpx is None:
        init_clients()
    if _httpx is None:
        raise RuntimeError("httpx client not initialized")
    return _httpx


async def close_clients() -> None:
    global _redis, _httpx, _minio_private, _minio_public
    if _redis is not None:
        await _redis.close()
        _redis = None
    if _httpx is not None:
        await _httpx.aclose()
        _httpx = None
    _minio_private = None
    _minio_public = None
