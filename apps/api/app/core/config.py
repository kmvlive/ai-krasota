"""Конфигурация приложения (pydantic-settings). Значения берутся из .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Общие
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "AI-krasota"
    BASE_DOMAIN: str = "localhost"

    # База данных / кэш
    DATABASE_URL: str = "postgresql+asyncpg://aikrasota:aikrasota@localhost:5432/aikrasota"
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"

    # Безопасность
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 60  # длинные сессии (PRD §15.1)
    FRONTEND_ORIGIN: str = "http://localhost:3000"

    # AI (Timeweb, PRD §9)
    TIMEWEB_AI_API_KEY: str = ""
    TIMEWEB_AI_MODEL: str = "dashscope/qwen3.5-flash"

    # Триал (PRD §12.2)
    TRIAL_DAYS: int = 14


@lru_cache
def get_settings() -> Settings:
    return Settings()
