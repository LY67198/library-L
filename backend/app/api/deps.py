from __future__ import annotations

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


async def get_db(request: Request) -> AsyncSession:
    """FastAPI dependency wrapper around get_db_dependency."""
    async for session in get_db_dependency():
        yield session


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract JWT, decode, fetch user. Sets request.state.user_id and request.state.tenant_id."""
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
