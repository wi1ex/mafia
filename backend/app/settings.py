from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    ENV: str = "production"
    PROJECT_NAME: str = "Mafia"
    DOMAIN: str
    PUBLIC_URL: str

    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None

    MINIO_ENDPOINT: str
    MINIO_ROOT_USER: str
    MINIO_ROOT_PASSWORD: str
    MINIO_BUCKET: str

    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    LIVEKIT_WS_PUBLIC: str
    LIVEKIT_API_KEY: str
    LIVEKIT_API_SECRET: str

    TG_BOT_TOKEN: str

    BACKEND_CORS_ORIGINS: List[str] = []

settings = Settings()
if not settings.BACKEND_CORS_ORIGINS:
    settings.BACKEND_CORS_ORIGINS = [settings.PUBLIC_URL]
