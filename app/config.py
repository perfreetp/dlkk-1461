from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./petct_scheduler.db"

    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "PET-CT Scheduler Service"
    DEBUG: bool = True

    MAX_CONSECUTIVE_NO_SHOW: int = 3
    CHECKIN_TIMEOUT_MINUTES: int = 30
    DRUG_WASTE_THRESHOLD: float = 0.15

    SMTP_HOST: str = "smtp.example.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "notification@example.com"
    SMTP_PASSWORD: str = "your-password"

    CORS_ORIGINS: List[str] = ["*"]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
