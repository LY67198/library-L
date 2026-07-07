"""JWT is_admin claim 和 admin 权限校验测试"""
import pytest
from unittest.mock import MagicMock

from core.security import create_access_token, decode_token
from models import User


def make_user(is_admin: bool = False):
    user = MagicMock(spec=User)
    user.id = "test-user-id"
    user.is_admin = is_admin
    return user


async def test_access_token_contains_is_admin():
    user = make_user(is_admin=True)
    token = create_access_token(user)
    payload = decode_token(token)
    assert payload["is_admin"] is True


async def test_access_token_is_admin_false():
    user = make_user(is_admin=False)
    token = create_access_token(user)
    payload = decode_token(token)
    assert payload["is_admin"] is False


async def test_decode_token_extracts_is_admin():
    user = make_user(is_admin=True)
    token = create_access_token(user)
    payload = decode_token(token)
    assert "is_admin" in payload
    assert payload["is_admin"] is True
