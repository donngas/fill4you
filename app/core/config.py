from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
# Load local development configuration without overriding actual process environment values.
load_dotenv(ENV_FILE, override=False)


class Settings(BaseSettings):
    app_name: str = "fill4you"
    app_env: str = "development"
    postgres_db: str = "fill4you"
    postgres_user: str = "fill4you"
    postgres_password: str = "fill4you"
    postgres_host: str = "db"
    postgres_port: int = 5432
    session_secret: str = "change-this-development-secret"
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    google_token_encryption_key: str | None = None
    google_sync_past_days: int = 7
    google_sync_future_days: int = 90
    google_sync_interval_minutes: int = 15
    session_cookie_name: str = "fill4you_session"
    session_cookie_domain: str | None = None
    session_same_site: str = "lax"
    session_https_only: bool = False
    cors_allowed_origins: list[str] = []
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_workers: int = 1
    app_log_level: str = "info"
    development_user_email: str = "developer@fill4you.local"

    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    @field_validator("app_env")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        allowed = {"development", "production", "test"}
        if value not in allowed:
            raise ValueError(f"APP_ENV must be one of: {', '.join(sorted(allowed))}")
        return value

    @field_validator("session_cookie_domain", mode="before")
    @classmethod
    def normalize_empty_cookie_domain(cls, value: str | None) -> str | None:
        return value or None

    @field_validator(
        "google_sync_past_days", "google_sync_future_days", "google_sync_interval_minutes"
    )
    @classmethod
    def validate_positive_google_sync_value(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Google Calendar sync values must be at least 1")
        return value

    @model_validator(mode="after")
    def require_secure_production_session_secret(self) -> "Settings":
        if self.app_env == "production":
            if self.session_secret == "change-this-development-secret":
                raise ValueError("SESSION_SECRET must be set in production")
            if not self.session_https_only:
                raise ValueError("SESSION_HTTPS_ONLY must be true in production")
            if self.postgres_password == "fill4you":
                raise ValueError("POSTGRES_PASSWORD must be set in production")
        return self

    @property
    def development_login_enabled(self) -> bool:
        return self.app_env == "development"

    @property
    def session_https_only_enabled(self) -> bool:
        return self.session_https_only

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def google_calendar_configured(self) -> bool:
        return bool(self.google_oauth_configured and self.google_token_encryption_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
