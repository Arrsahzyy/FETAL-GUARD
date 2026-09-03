from functools import lru_cache
from pathlib import Path
import secrets
from typing import Literal
from urllib.parse import urlsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_PATH = BASE_DIR / "fetal_guard.db"
_DEV_SECRET_KEY = secrets.token_urlsafe(48)
# Loopback/test hosts are the development default. A production deployment that
# never sets TRUSTED_HOSTS would still pass an "explicit and non-wildcard" check
# while TrustedHostMiddleware rejects every real Host header with 400, so
# production must name at least one host outside this set.
DEV_TRUSTED_HOSTS = ["localhost", "127.0.0.1", "testserver"]


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
    # Claim codes are short enough to guess without throttling, so failures are
    # counted per caller and per targeted device UID.
    DEVICE_CLAIM_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    DEVICE_CLAIM_RATE_LIMIT_WINDOW_MINUTES: int = 15
    DEVICE_CLAIM_RATE_LIMIT_LOCKOUT_MINUTES: int = 15

    # Database
    SQLALCHEMY_DATABASE_URI: str = f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
    # Migrations must run as the table-owning role, which is disallowed at runtime
    # by assert_postgresql_runtime_isolation. Falls back to SQLALCHEMY_DATABASE_URI
    # when unset (dev/SQLite, or single-role deployments).
    ALEMBIC_DATABASE_URI: str | None = None
    AUTO_CREATE_DB: bool = True
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost",
        "https://localhost",
        "capacitor://localhost",
    ]
    TRUSTED_HOSTS: list[str] = list(DEV_TRUSTED_HOSTS)
    TRUSTED_PROXY_IPS: list[str] = []
    PATIENT_SELF_REGISTRATION_MODE: Literal["disabled", "single_facility"] = "single_facility"
    PATIENT_REGISTRATION_ORGANIZATION_ID: str | None = None
    REQUIRE_POSTGRES_RLS: bool = True
    # When true, a telemetry chunk is only stored if it carries a valid HMAC from
    # the device's provisioned secret. Kept opt-in for local bring-up so an
    # unsigned bench device still works, but mandatory in production.
    REQUIRE_DEVICE_PACKET_SIGNATURE: bool = False
    REALTIME_EVENT_RETENTION_HOURS: int = 72
    AI_PIPELINE_MODE: Literal["disabled", "research", "shadow", "clinician"] = "disabled"
    AI_ACTIVE_MODEL_VERSION_ID: str | None = None
    AI_WINDOW_SECONDS: int = 60
    AI_WINDOW_STRIDE_SECONDS: int = 15
    AI_LATE_ARRIVAL_GRACE_SECONDS: int = 10
    AI_MIN_VALID_RATIO: float = 0.8
    AI_MAX_JOB_ATTEMPTS: int = 3
    AI_JOB_LEASE_SECONDS: int = 120

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
    def require_safe_production_configuration(self) -> "Settings":
        if not 1 <= self.REALTIME_EVENT_RETENTION_HOURS <= 720:
            raise ValueError("REALTIME_EVENT_RETENTION_HOURS must be between 1 and 720")
        if not 10 <= self.AI_WINDOW_SECONDS <= 600:
            raise ValueError("AI_WINDOW_SECONDS must be between 10 and 600")
        if not 1 <= self.AI_WINDOW_STRIDE_SECONDS <= self.AI_WINDOW_SECONDS:
            raise ValueError("AI_WINDOW_STRIDE_SECONDS must be between 1 and AI_WINDOW_SECONDS")
        if not 0 <= self.AI_LATE_ARRIVAL_GRACE_SECONDS <= 120:
            raise ValueError("AI_LATE_ARRIVAL_GRACE_SECONDS must be between 0 and 120")
        if not 0 < self.AI_MIN_VALID_RATIO <= 1:
            raise ValueError("AI_MIN_VALID_RATIO must be in (0, 1]")
        if not 1 <= self.AI_MAX_JOB_ATTEMPTS <= 10:
            raise ValueError("AI_MAX_JOB_ATTEMPTS must be between 1 and 10")
        if not 30 <= self.AI_JOB_LEASE_SECONDS <= 3600:
            raise ValueError("AI_JOB_LEASE_SECONDS must be between 30 and 3600")
        if self.AI_PIPELINE_MODE != "disabled" and not self.AI_ACTIVE_MODEL_VERSION_ID:
            raise ValueError("AI_ACTIVE_MODEL_VERSION_ID is required when the AI pipeline is enabled")
        if self.ENVIRONMENT != "production":
            return self
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY is required when ENVIRONMENT=production")
        if self.SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
            raise ValueError("SQLite is not supported when ENVIRONMENT=production")
        if self.AUTO_CREATE_DB:
            raise ValueError("AUTO_CREATE_DB must be false when ENVIRONMENT=production")
        if not self.BACKEND_CORS_ORIGINS:
            raise ValueError("Production CORS origins must use HTTPS and must be explicit")
        for origin in self.BACKEND_CORS_ORIGINS:
            normalized_origin = origin.strip()
            parsed_origin = urlsplit(normalized_origin)
            unsafe_origin = (
                normalized_origin != origin
                or normalized_origin.lower() in {"*", "null"}
                or parsed_origin.scheme.lower() != "https"
                or not parsed_origin.hostname
                or parsed_origin.username is not None
                or parsed_origin.password is not None
                or bool(parsed_origin.path)
                or bool(parsed_origin.query)
                or bool(parsed_origin.fragment)
                or "*" in parsed_origin.hostname
            )
            if unsafe_origin:
                raise ValueError("Production CORS origins must use HTTPS and must be explicit")
        if not self.TRUSTED_HOSTS or "*" in self.TRUSTED_HOSTS:
            raise ValueError("Production TRUSTED_HOSTS must be explicit")
        production_hosts = {host.strip().lower() for host in self.TRUSTED_HOSTS if host.strip()}
        if not production_hosts:
            raise ValueError("Production TRUSTED_HOSTS must be explicit")
        if "testserver" in production_hosts:
            raise ValueError("Production TRUSTED_HOSTS must not include the testserver host")
        if production_hosts <= {host.lower() for host in DEV_TRUSTED_HOSTS}:
            raise ValueError(
                "Production TRUSTED_HOSTS must name the deployment hostname, not only loopback defaults"
            )
        if self.ACCESS_TOKEN_EXPIRE_MINUTES > 60:
            raise ValueError("Production access tokens may not exceed 60 minutes")
        if self.REFRESH_TOKEN_EXPIRE_DAYS > 30:
            raise ValueError("Production refresh tokens may not exceed 30 days")
        if (
            self.PATIENT_SELF_REGISTRATION_MODE == "single_facility"
            and not self.PATIENT_REGISTRATION_ORGANIZATION_ID
        ):
            raise ValueError(
                "PATIENT_REGISTRATION_ORGANIZATION_ID is required for production single-facility registration"
            )
        if not self.REQUIRE_POSTGRES_RLS:
            raise ValueError("REQUIRE_POSTGRES_RLS must be true in production")
        if not self.REQUIRE_DEVICE_PACKET_SIGNATURE:
            raise ValueError("REQUIRE_DEVICE_PACKET_SIGNATURE must be true in production")
        return self

    @property
    def jwt_secret_key(self) -> str:
        return self.SECRET_KEY or _DEV_SECRET_KEY


@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
