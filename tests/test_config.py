import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_requires_secure_session_settings() -> None:
    with pytest.raises(ValidationError, match="SESSION_HTTPS_ONLY"):
        Settings(app_env="production", session_secret="a-secure-secret")


def test_empty_cookie_domain_is_treated_as_unset() -> None:
    settings = Settings(session_cookie_domain="")

    assert settings.session_cookie_domain is None
