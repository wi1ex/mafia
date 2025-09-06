from __future__ import annotations
from typing import Optional
import httpx
import redis.asyncio as redis
from minio import Minio
from ..settings import settings

_redis: Optional[redis.Redis] = None
_minio_private: Optional[Minio] = None
_minio_public: Optional[Minio] = None
_httpx: Optional[httpx.AsyncClient] = None

def init_clients() -> None:
    global _redis, _minio_private, _minio_public, _httpx
    if _redis is None:
        _redis = redis.Redis(
            host=settings.REDIS_HOST, port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD, decode_responses=True,
        )
    if _minio_private is None:
        _minio_private = Minio(
            settings.MINIO_ENDPOINT,  # "minio:9000"
            access_key=settings.MINIO_ROOT_USER,
            secret_key=settings.MINIO_ROOT_PASSWORD,
            secure=False,
        )
    if _minio_public is None:
        _minio_public = Minio(
            settings.DOMAIN,  # без схемы
            access_key=settings.MINIO_ROOT_USER,
            secret_key=settings.MINIO_ROOT_PASSWORD,
            secure=True,
            region="us-east-1",
        )
    if _httpx is None:
        _httpx = httpx.AsyncClient(timeout=5.0)  # общий пул для внешних HTTP-запросов

def get_redis() -> redis.Redis:
    assert _redis is not None, "redis not initialized"
    return _redis

def get_minio_private() -> Minio:
    assert _minio_private is not None, "minio private not initialized"
    return _minio_private

def get_minio_public() -> Minio:
    assert _minio_public is not None, "minio public not initialized"
    return _minio_public

def get_httpx() -> httpx.AsyncClient:
    assert _httpx is not None, "httpx not initialized"
    return _httpx

async def close_clients() -> None:
    global _redis, _httpx
    # redis имеет встроенный пул, закрывать необязательно, но корректно:
    if _redis is not None:
        await _redis.close()
    if _httpx is not None:
        await _httpx.aclose()
