"""认证路由 — 提供注册、登录、刷新令牌、当前用户查询等 JWT 鉴权相关接口。"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.core.exceptions import Unauthorized
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models import User
from app.schemas.auth import (
    AccessTokenResponse,
    CurrentUserResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserInfo,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


async def _resolve_default_tenant(db: AsyncSession) -> UUID:
    """解析 MVP 阶段默认租户 — 通过 settings 中的 default_tenant_code 查找种子租户。

    参数:
        db: 异步数据库会话,用于查询 Tenant 表。

    返回值:
        UUID: 默认租户的主键 ID。

    抛出:
        RuntimeError: 当默认租户尚未初始化(未运行 scripts/init_db.py)时抛出。
    """
    from sqlalchemy import select
    from app.models import Tenant

    settings = get_settings()
    stmt = select(Tenant).where(Tenant.code == settings.default_tenant_code)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise RuntimeError(
            f"Default tenant '{settings.default_tenant_code}' not seeded. "
            "Run scripts/init_db.py first."
        )
    return tenant.id


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """用户注册 — 创建新用户并返回 access/refresh 双令牌。

    参数:
        payload: 注册请求体,包含学号、密码、姓名、邮箱。
        db: 异步数据库会话,用于写入新用户。

    返回值:
        TokenResponse: 包含访问令牌、刷新令牌、过期时间与用户信息的响应。
    """
    tenant_id = await _resolve_default_tenant(db)
    service = UserService(db)
    user = await service.register(
        tenant_id=tenant_id,
        student_no=payload.student_no,
        password=payload.password,
        full_name=payload.full_name,
        email=payload.email,
    )

    access_token, _, access_ttl = create_access_token(
        user_id=user.id, tenant_id=tenant_id, roles=[user.role]
    )
    refresh_token, _ = create_refresh_token(user_id=user.id, tenant_id=tenant_id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=access_ttl,
        user=UserInfo(
            id=user.id,
            student_no=user.student_no,
            full_name=user.full_name,
            email=user.email,
            role=user.role,
            tenant_id=str(tenant_id),
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """用户登录 — 校验账号密码,成功后下发 access/refresh 双令牌。

    参数:
        payload: 登录请求体,包含学号与密码。
        db: 异步数据库会话,用于查询用户与鉴权。

    返回值:
        TokenResponse: 包含访问令牌、刷新令牌、过期时间与用户信息的响应。
    """
    tenant_id = await _resolve_default_tenant(db)
    service = UserService(db)
    user = await service.authenticate(
        tenant_id=tenant_id, student_no=payload.student_no, password=payload.password
    )
    access_token, _, access_ttl = create_access_token(
        user_id=user.id, tenant_id=tenant_id, roles=[user.role]
    )
    refresh_token, _ = create_refresh_token(user_id=user.id, tenant_id=tenant_id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=access_ttl,
        user=UserInfo(
            id=user.id,
            student_no=user.student_no,
            full_name=user.full_name,
            email=user.email,
            role=user.role,
            tenant_id=str(tenant_id),
        ),
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> AccessTokenResponse:
    """刷新访问令牌 — 使用 refresh token 换发新的 access token。

    参数:
        payload: 刷新请求体,包含 refresh token。
        db: 异步数据库会话,用于根据 token 中的 sub 加载用户。

    返回值:
        AccessTokenResponse: 包含新的访问令牌与过期时间。

    抛出:
        Unauthorized: 当 token 类型不是 refresh 时抛出。
    """
    token_payload = decode_token(payload.refresh_token)
    if token_payload.get("type") != "refresh":
        raise Unauthorized("Token is not a refresh token")

    user_id = int(token_payload["sub"])
    tenant_id = UUID(token_payload["tenant_id"])

    service = UserService(db)
    user = await service.get(user_id, tenant_id)

    access_token, _, access_ttl = create_access_token(
        user_id=user.id, tenant_id=tenant_id, roles=[user.role]
    )
    return AccessTokenResponse(access_token=access_token, expires_in=access_ttl)


@router.get("/me", response_model=CurrentUserResponse)
async def me(
    request: Request,
    user: User = Depends(get_current_user),
) -> CurrentUserResponse:
    """查询当前登录用户信息 — 返回当前 token 对应的用户与租户上下文。

    参数:
        request: FastAPI 请求对象,用于读取 request.state.tenant_id 与 roles。
        user: 通过 get_current_user 依赖注入得到的当前用户。

    返回值:
        CurrentUserResponse: 包含当前用户基本信息、租户 ID 与角色集合。
    """
    return CurrentUserResponse(
        user=UserInfo(
            id=user.id,
            student_no=user.student_no,
            full_name=user.full_name,
            email=user.email,
            role=user.role,
            tenant_id=str(request.state.tenant_id),
        ),
        tenant_id=str(request.state.tenant_id),
        roles=list(request.state.roles),
    )
