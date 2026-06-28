"""FastAPI 依赖注入模块 — 提供数据库会话与当前登录用户等可在路由中复用的依赖项。"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_dependency
from app.core.exceptions import Unauthorized
from app.core.security import decode_token
from app.models import User
from app.services.user_service import UserService

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 数据库会话依赖 — 包装核心层的 get_db_dependency,为每个请求产出一个 AsyncSession。

    这是一个 async generator(用 yield 产出),FastAPI 会负责在请求结束时关闭它。

    参数:
        request: FastAPI 请求对象(底层未直接使用,但 FastAPI 依赖注入框架要求)。

    返回值:
        AsyncGenerator[AsyncSession, None]: 异步生成器,每次产出可用的 AsyncSession。
    """
    async for session in get_db_dependency():
        yield session


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """解析当前请求的 JWT 并返回对应用户。

    从 Authorization Bearer 头提取 access token,解码后校验类型,再加载用户实体。
    同时将 user_id / tenant_id / roles 写入 request.state,供后续依赖或中间件复用。

    参数:
        request: FastAPI 请求对象,用于写入解析后的用户上下文。
        credentials: FastAPI 提取的 Bearer 凭据,依赖 HTTPBearer 安全方案。
        db: 异步数据库会话,用于按 user_id 加载用户记录。

    返回值:
        User: 当前请求对应的已登录用户实体。
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise Unauthorized("Missing bearer token")

    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise Unauthorized("Token is not an access token")

    user_id = int(payload["sub"])
    tenant_id = UUID(payload["tenant_id"])

    request.state.user_id = user_id
    request.state.tenant_id = tenant_id
    request.state.roles = set(payload.get("roles", []))

    service = UserService(db)
    return await service.get(user_id, tenant_id)
