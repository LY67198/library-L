"""安全模块 — JWT 签发/验证 + 密码哈希"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from backend.config.settings import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def _is_admin_from_user(user_or_data) -> bool:
    """从 User 对象或字典中提取 is_admin"""
    if isinstance(user_or_data, dict):
        return bool(user_or_data.get("is_admin", False))
    return bool(getattr(user_or_data, "is_admin", False))


def _resolve_user_id(user_or_data) -> str:
    """从 User 对象、字典或字符串中提取用户 ID"""
    if isinstance(user_or_data, str):
        return user_or_data
    if isinstance(user_or_data, dict):
        return user_or_data["sub"]
    return user_or_data.id


def create_access_token(user_or_data) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    user_id = _resolve_user_id(user_or_data)
    is_admin = _is_admin_from_user(user_or_data)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "access",
        "is_admin": is_admin,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_or_data) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    user_id = _resolve_user_id(user_or_data)
    is_admin = _is_admin_from_user(user_or_data)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
        "is_admin": is_admin,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        raise ValueError("invalid_token")
