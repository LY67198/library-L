"""JWT 安全模块测试 — 验证 access/refresh token 的签发、解码、非法与过期 token 的处理。"""
import time
from uuid import uuid4

import pytest

from app.core.exceptions import Unauthorized
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)


def test_access_token_round_trip():
    """测试 access token 往返:TTL=3600,sub/tenant_id/roles/jti/type 字段均能在解码后正确还原。"""
    user_id = 42
    tenant_id = uuid4()
    token, jti, ttl = create_access_token(user_id=user_id, tenant_id=tenant_id, roles=["student"])
    assert ttl == 3600
    payload = decode_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["roles"] == ["student"]
    assert payload["jti"] == jti
    assert payload["type"] == "access"


def test_refresh_token_round_trip():
    """测试 refresh token 往返:type=refresh 且 sub 字段等于原 user_id,用于刷新 access token。"""
    user_id = 42
    tenant_id = uuid4()
    token, jti = create_refresh_token(user_id=user_id, tenant_id=tenant_id)
    payload = decode_token(token)
    assert payload["type"] == "refresh"
    assert payload["sub"] == str(user_id)


def test_decode_invalid_token_raises():
    """测试解码非法 JWT 字符串:应抛出 Unauthorized 异常,避免无效 token 通过校验。"""
    with pytest.raises(Unauthorized):
        decode_token("not-a-real-jwt-token")


def test_decode_expired_token_raises(monkeypatch):
    """测试过期 token:把 TTL 设为 1 秒并 sleep 2 秒后解码,应抛出 Unauthorized 异常。"""
    from app.core import security

    # Patch settings to force 1-second TTL
    class FakeSettings:
        jwt_secret = "x" * 32
        jwt_algorithm = "HS256"
        jwt_access_ttl_seconds = 1

    monkeypatch.setattr(security, "get_settings", lambda: FakeSettings())
    token, _, _ = create_access_token(user_id=1, tenant_id=uuid4(), roles=[])
    time.sleep(2)
    with pytest.raises(Unauthorized):
        decode_token(token)
