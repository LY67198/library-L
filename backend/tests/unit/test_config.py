import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_load_defaults(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    settings = Settings()
    assert settings.app_env == "development"
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.jwt_algorithm == "HS256"
    assert settings.jwt_access_ttl_seconds == 3600


def test_settings_override_from_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret123")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    settings = Settings()
    assert settings.app_env == "production"
    assert "secret123" in settings.database_url


def test_settings_database_url_async(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "x")
    monkeypatch.setenv("JWT_SECRET", "y" * 32)
    settings = Settings()
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.database_url_sync.startswith("postgresql://")


def test_settings_invalid_env_raises(monkeypatch):
    monkeypatch.setenv("APP_ENV", "invalid_env_value")
    with pytest.raises(ValidationError):
        Settings()
