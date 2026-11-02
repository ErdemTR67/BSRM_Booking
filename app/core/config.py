from functools import lru_cache
import re
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Bosphoreum Booking API"
    app_environment: Literal["development", "test", "production"] = "development"
    app_debug: bool = False
    database_url: str
    database_migration_url: str | None = None
    database_application_role: str = "bsrm_booking_app"
    jwt_secret_key: SecretStr
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=30, gt=0, le=1440)
    refresh_token_expire_days: int = Field(default=30, gt=0, le=365)
    cors_origins: list[str] = Field(default_factory=list)
    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["127.0.0.1", "localhost", "testserver"]
    )
    expose_api_docs: bool = True
    jwt_issuer: str = "bsrm-booking"
    jwt_audience: str = "bsrm-booking-api"
    invitation_expire_hours: int = Field(default=48, ge=1, le=168)
    invitation_frontend_url: str = "http://localhost:5173/accept-invitation"
    email_delivery_mode: Literal["console", "smtp"] = "console"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: str | None = None
    smtp_use_tls: bool = True
    public_booking_challenge_mode: Literal["disabled", "turnstile"] = "disabled"
    turnstile_secret_key: SecretStr | None = None
    turnstile_verify_url: str = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    turnstile_expected_action: str = Field(
        default="booking", min_length=1, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    public_booking_catalogue_rate_limit: int = Field(default=120, ge=1, le=10_000)
    public_booking_availability_rate_limit: int = Field(default=60, ge=1, le=10_000)
    public_booking_create_rate_limit: int = Field(default=5, ge=1, le=1_000)
    public_booking_max_body_bytes: int = Field(default=16_384, ge=1_024, le=1_048_576)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("app_environment")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("database_application_role")
    @classmethod
    def validate_database_role(cls, value: str) -> str:
        normalized = value.strip()
        if re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", normalized) is None:
            raise ValueError("DATABASE_APPLICATION_ROLE is not a valid PostgreSQL role name.")
        return normalized

    @field_validator("cors_origins")
    @classmethod
    def normalize_cors_origins(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(origin.strip().rstrip("/") for origin in value if origin.strip()))

    @field_validator("allowed_hosts")
    @classmethod
    def normalize_allowed_hosts(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(host.strip().lower() for host in value if host.strip()))

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.app_environment != "production":
            return self

        secret = self.jwt_secret_key.get_secret_value()
        weak_markers = ("change-me", "changeme", "replace-me", "replace_with")
        if len(secret) < 32 or any(marker in secret.lower() for marker in weak_markers):
            raise ValueError("JWT_SECRET_KEY must be a strong secret in production.")
        if "*" in self.cors_origins:
            raise ValueError("Wildcard CORS origins are forbidden in production.")
        if self.app_debug:
            raise ValueError("APP_DEBUG must be false in production.")
        if self.expose_api_docs:
            raise ValueError("EXPOSE_API_DOCS must be false in production.")
        if not self.allowed_hosts or "*" in self.allowed_hosts:
            raise ValueError("ALLOWED_HOSTS must be explicit in production.")
        if not self.invitation_frontend_url.lower().startswith("https://"):
            raise ValueError("INVITATION_FRONTEND_URL must use HTTPS in production.")
        if self.email_delivery_mode != "smtp":
            raise ValueError("EMAIL_DELIVERY_MODE must be smtp in production.")
        if not self.smtp_host or not self.smtp_from_email:
            raise ValueError("SMTP_HOST and SMTP_FROM_EMAIL are required in production.")
        if self.smtp_username and self.smtp_password is None:
            raise ValueError("SMTP_PASSWORD is required when SMTP_USERNAME is configured.")
        if self.public_booking_challenge_mode != "turnstile":
            raise ValueError("PUBLIC_BOOKING_CHALLENGE_MODE must be turnstile in production.")
        if self.turnstile_secret_key is None:
            raise ValueError("TURNSTILE_SECRET_KEY is required in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
