import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_requires_secure_session_settings() -> None:
    with pytest.raises(ValidationError, match="SESSION_HTTPS_ONLY"):
        Settings(
            app_env="production",
            session_secret="a-secure-secret-that-is-long-enough",
            allowed_hosts=["fill4you.example"],
        )


def test_google_oauth_credentials_must_be_configured_together() -> None:
    with pytest.raises(ValidationError, match="set together"):
        Settings(google_client_id="client-id", google_client_secret=None)


def test_production_google_oauth_requires_token_encryption_key() -> None:
    with pytest.raises(ValidationError, match="GOOGLE_TOKEN_ENCRYPTION_KEY"):
        Settings(
            app_env="production",
            session_secret="a-secure-secret-that-is-long-enough",
            session_https_only=True,
            postgres_password="not-the-default",
            allowed_hosts=["fill4you.example"],
            google_client_id="client-id",
            google_client_secret="client-secret",
            google_token_encryption_key=None,
        )


def test_empty_cookie_domain_is_treated_as_unset() -> None:
    settings = Settings(session_cookie_domain="")

    assert settings.session_cookie_domain is None


def test_database_url_is_built_from_postgres_settings() -> None:
    settings = Settings(
        postgres_db="schedule",
        postgres_user="student",
        postgres_password="pass word",
        postgres_host="postgres.example",
        postgres_port=5433,
    )

    assert settings.database_url.drivername == "postgresql+psycopg"
    assert settings.database_url.username == "student"
    assert settings.database_url.password == "pass word"
    assert settings.database_url.host == "postgres.example"
    assert settings.database_url.port == 5433
    assert settings.database_url.database == "schedule"


def test_environment_variables_override_development_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_NAME", "fill4you-test")
    monkeypatch.setenv("APP_PORT", "9010")
    monkeypatch.setenv("POSTGRES_HOST", "test-db")

    settings = Settings()

    assert settings.app_name == "fill4you-test"
    assert settings.app_port == 9010
    assert settings.postgres_host == "test-db"
