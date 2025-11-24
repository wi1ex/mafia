from __future__ import annotations
import structlog
import httpx
import redis.asyncio as redis
from minio import Minio
from ..core.settings import settings

log = structlog.get_logger()

_redis: redis.Redis | None = None
_minio_private: Minio | None = None
_minio_public: Minio | None = None
_httpx: httpx.AsyncClient | None = None


def _build_redis() -> redis.Redis:
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD or None,
        decode_responses=True,
        socket_keepalive=True,
        health_check_interval=10,
        socket_connect_timeout=3.0,
        socket_timeout=5.0,
        retry_on_timeout=True,
    )


def _build_minio_private() -> Minio:
    return Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ROOT_USER,
        secret_key=settings.MINIO_ROOT_PASSWORD,
        secure=False,
    )


def _build_minio_public() -> Minio:
    return Minio(
        endpoint=settings.DOMAIN,
        access_key=settings.MINIO_ROOT_USER,
        secret_key=settings.MINIO_ROOT_PASSWORD,
        region="us-east-1",
        secure=True,
    )


def _build_httpx() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(5.0, read=10.0, write=5.0, connect=5.0),
        limits=httpx.Limits(max_keepalive_connections=100, max_connections=200),
        follow_redirects=True,
        headers={"User-Agent": "backend/1.0"},
    )


def init_clients() -> None:
    global _redis, _minio_private, _minio_public, _httpx
    if _redis and _minio_private and _minio_public and _httpx:
        return

    log.info("clients.init.start")
    _redis = _redis or _build_redis()
    _minio_private = _minio_private or _build_minio_private()
    _minio_public = _minio_public or _build_minio_public()
    _httpx = _httpx or _build_httpx()
    log.info("clients.init.ok")


def get_redis() -> redis.Redis:
    if _redis is None:
        log.error("clients.redis.uninitialized")
        raise RuntimeError("redis client not initialized")
    return _redis


def get_minio_private() -> Minio:
    if _minio_private is None:
        log.error("clients.minio_private.uninitialized")
        raise RuntimeError("minio private client not initialized")
    return _minio_private


def get_minio_public() -> Minio:
    if _minio_public is None:
        log.error("clients.minio_public.uninitialized")
        raise RuntimeError("minio public client not initialized")
    return _minio_public


def get_httpx() -> httpx.AsyncClient:
    if _httpx is None:
        log.error("clients.httpx.uninitialized")
        raise RuntimeError("httpx client not initialized")
    return _httpx


async def close_clients() -> None:
    global _redis, _httpx, _minio_private, _minio_public
    log.info("clients.close.start")
    if _redis is not None:
        await _redis.close()
        _redis = None
    if _httpx is not None:
        await _httpx.aclose()
        _httpx = None
    _minio_private = None
    _minio_public = None
    log.info("clients.close.ok")
