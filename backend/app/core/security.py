"""安全模块 — 密码哈希与 JWT 双 Token(access / refresh)签发与解析。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """使用 bcrypt 将明文密码哈希后返回。

    参数:
        plain: 明文密码。

    返回值:
        str: bcrypt 哈希串。
    """
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配,异常时返回 False(不抛错)。

    参数:
        plain: 待校验的明文密码。
        hashed: 已存在的密码哈希串。

    返回值:
        bool: 校验通过返回 True,否则 False。
    """
    try:
        return _pwd_context.verify(plain, hashed)
    except (ValueError, TypeError):
        return False


def create_access_token(
    *,
    user_id: int,
    tenant_id: UUID,
    roles: list[str],
    expires_in: int | None = None,
) -> tuple[str, str, int]:
    """签发 access JWT,载荷包含 sub / tenant_id / roles / jti / type。

    参数:
        user_id: 用户 ID,会写入 sub 字段。
        tenant_id: 租户 ID,用于多租户隔离。
        roles: 该用户拥有的角色列表。
        expires_in: 可选的自定义过期秒数;为空时使用配置中的默认 TTL。

    返回值:
        tuple[str, str, int]: (token, jti, expires_in_seconds) 三元组。
    """
    settings = get_settings()
    expires_in = expires_in or settings.jwt_access_ttl_seconds
    jti = str(uuid4())
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
        "jti": jti,
        "type": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti, expires_in


def create_refresh_token(*, user_id: int, tenant_id: UUID) -> tuple[str, str]:
    """签发 refresh JWT,载荷包含 sub / tenant_id / jti / type,有效期较长。

    参数:
        user_id: 用户 ID,会写入 sub 字段。
        tenant_id: 租户 ID。

    返回值:
        tuple[str, str]: (token, jti) 二元组。
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    jti = str(uuid4())
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_refresh_ttl_seconds)).timestamp()),
        "jti": jti,
        "type": "refresh",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti


def decode_token(token: str) -> dict[str, Any]:
    """解析并校验 JWT,失败时抛 ``Unauthorized``。

    参数:
        token: 待解析的 JWT 字符串。

    返回值:
        dict[str, Any]: 解码后的载荷字典。
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as e:
        from app.core.exceptions import Unauthorized
        raise Unauthorized(f"Invalid token: {e}") from e