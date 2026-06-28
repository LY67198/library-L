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
    """MVP: single default tenant."""
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
