"""安全模块单元测试"""

import pytest
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password():
    plain = "mypassword123"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed)
    assert not verify_password("wrongpassword", hashed)


def test_create_and_decode_access_token():
    token = create_access_token("user-1")
    payload = decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_create_and_decode_refresh_token():
    token = create_refresh_token("user-1")
    payload = decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["type"] == "refresh"


def test_decode_invalid_token():
    with pytest.raises(ValueError, match="invalid_token"):
        decode_token("not.a.valid.token")


def test_refresh_token_rejected_as_access():
    refresh = create_refresh_token("user-1")
    payload = decode_token(refresh)
    assert payload["type"] == "refresh"
    assert payload["type"] != "access"
