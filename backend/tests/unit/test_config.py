"""配置模块测试 — 验证 Settings 的默认值、环境变量覆盖、URL 派生与非法值校验。"""
import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_load_defaults(monkeypatch):
    """测试无环境变量时:Settings 加载默认值,数据库 URL 走 asyncpg,JWT 算法为 HS256、TTL 为 3600。"""
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    settings = Settings()
    assert settings.app_env == "development"
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.jwt_algorithm == "HS256"
    assert settings.jwt_access_ttl_seconds == 3600


def test_settings_override_from_env(monkeypatch):
    """测试环境变量覆盖:APP_ENV=production 与 POSTGRES_PASSWORD=secret123 应被 Settings 正确读取。"""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret123")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    settings = Settings()
    assert settings.app_env == "production"
    assert "secret123" in settings.database_url


def test_settings_database_url_async(monkeypatch):
    """测试数据库 URL 派生:async URL 走 asyncpg 驱动,sync URL 走原始 postgresql 协议。"""
    monkeypatch.setenv("POSTGRES_PASSWORD", "x")
    monkeypatch.setenv("JWT_SECRET", "y" * 32)
    settings = Settings()
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.database_url_sync.startswith("postgresql://")


def test_settings_invalid_env_raises(monkeypatch):
    """测试非法 APP_ENV 取值:应被 Pydantic 校验拦截并抛出 ValidationError。"""
    monkeypatch.setenv("APP_ENV", "invalid_env_value")
    with pytest.raises(ValidationError):
        Settings()
