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
    user_id = 42
    tenant_id = uuid4()
    token, jti = create_refresh_token(user_id=user_id, tenant_id=tenant_id)
    payload = decode_token(token)
    assert payload["type"] == "refresh"
    assert payload["sub"] == str(user_id)


def test_decode_invalid_token_raises():
    with pytest.raises(Unauthorized):
        decode_token("not-a-real-jwt-token")


def test_decode_expired_token_raises(monkeypatch):
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
