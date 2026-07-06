"""FastAPI 依赖 — 数据库会话 + 认证用户"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .security import decode_token
from models import User

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """从 Bearer token 中提取当前用户。无 token 时返回 None 表示匿名。"""
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None
    except ValueError:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user


async def get_required_user(
    user: User | None = Depends(get_current_user),
) -> User:
    """强制认证依赖 — 未登录返回 401"""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token", "message": "请先登录"},
        )
    return user
