from functools import lru_cache
from pathlib import Path
import secrets
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_PATH = BASE_DIR / "fetal_guard.db"
_DEV_SECRET_KEY = secrets.token_urlsafe(48)


class Settings(BaseSettings):
    PROJECT_NAME: str = "FETAL-GUARD API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: Literal["development", "test", "production"] = "development"

    # Security
    SECRET_KEY: str | None = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_MINUTES: int = 15
    LOGIN_RATE_LIMIT_LOCKOUT_MINUTES: int = 15

    # Database
    SQLALCHEMY_DATABASE_URI: str = f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
    AUTO_CREATE_DB: bool = True
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost",
        "capacitor://localhost",
    ]

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, value: str | None) -> str | None:
        if value is not None and len(value) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return value

    @model_validator(mode="after")
    def require_secret_key_in_production(self) -> "Settings":
        if self.ENVIRONMENT == "production" and not self.SECRET_KEY:
            raise ValueError("SECRET_KEY is required when ENVIRONMENT=production")
        return self

    @property
    def jwt_secret_key(self) -> str:
        return self.SECRET_KEY or _DEV_SECRET_KEY


@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
