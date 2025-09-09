from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    PROJECT_NAME: str
    DOMAIN: str

    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str

    MINIO_ENDPOINT: str
    MINIO_ROOT_USER: str
    MINIO_ROOT_PASSWORD: str
    MINIO_BUCKET: str

    TG_BOT_TOKEN: str
    JWT_SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int

    LIVEKIT_API_KEY: str
    LIVEKIT_API_SECRET: str

    BACKEND_CORS_ORIGINS: List[str] = []

settings = Settings()
if not settings.BACKEND_CORS_ORIGINS:
    settings.BACKEND_CORS_ORIGINS = [f"https://{settings.DOMAIN}"]
