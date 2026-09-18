from functools import lru_cache

from pydantic import PostgresDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "fill4you"
    app_env: str = "development"
    database_url: PostgresDsn = "postgresql+psycopg://fill4you:fill4you@db:5432/fill4you"
    session_secret: str = "change-this-development-secret"
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    session_cookie_name: str = "fill4you_session"
    session_cookie_domain: str | None = None
    session_same_site: str = "lax"
    session_https_only: bool = False
    cors_allowed_origins: list[str] = []
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_workers: int = 1
    app_log_level: str = "info"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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

    @model_validator(mode="after")
    def require_secure_production_session_secret(self) -> "Settings":
        if self.app_env == "production":
            if self.session_secret == "change-this-development-secret":
                raise ValueError("SESSION_SECRET must be set in production")
            if not self.session_https_only:
                raise ValueError("SESSION_HTTPS_ONLY must be true in production")
        return self

    @property
    def development_login_enabled(self) -> bool:
        return self.app_env == "development"

    @property
    def session_https_only_enabled(self) -> bool:
        return self.session_https_only

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
