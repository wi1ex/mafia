from __future__ import annotations
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    ACCESS_EXP_MIN: int
    REFRESH_EXP_DAY: int

    LIVEKIT_API_KEY: str
    LIVEKIT_API_SECRET: str

    BACKEND_CORS_ORIGINS: List[str] = []

    GAME_MIN_READY_PLAYERS: int = 5
    ROLE_PICK_SECONDS: int = 10
    ROLE_DECK: tuple[str, ...] = ("citizen", "citizen", "citizen", "citizen", "citizen", "citizen", "mafia", "mafia", "don", "sheriff")
    MAFIA_TALK_SECONDS: int = 5  # 60
    PLAYER_TALK_SECONDS: int = 60
    PLAYER_TALK_SHORT_SECONDS: int = 30
    PLAYER_FOUL_SECONDS: int = 4
    NIGHT_ACTION_SECONDS: int = 10
    VOTE_SECONDS: int = 5  # 3

    @property
    def pg_dsn(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def redis_url(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"


settings = Settings()


if not settings.BACKEND_CORS_ORIGINS:
    settings.BACKEND_CORS_ORIGINS = [f"https://{settings.DOMAIN}"]
