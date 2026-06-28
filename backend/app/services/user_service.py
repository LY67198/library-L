from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, NotFound, Unauthorized
from app.core.security import hash_password, verify_password
from app.models import User
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = UserRepository(session)

    async def register(
        self,
        *,
        tenant_id: UUID,
        student_no: str,
        password: str,
        full_name: str,
        email: str | None = None,
        role: str = "student",
    ) -> User:
        existing = await self.repo.get_by_student_no(student_no, tenant_id)
        if existing is not None:
            raise Conflict(f"Student number {student_no} already exists")
        return await self.repo.create(
            tenant_id=tenant_id,
            student_no=student_no,
            password_hash=hash_password(password),
            full_name=full_name,
            email=email,
            role=role,
        )

    async def authenticate(
        self, *, tenant_id: UUID, student_no: str, password: str
    ) -> User:
        user = await self.repo.get_by_student_no(student_no, tenant_id)
        if user is None:
            raise Unauthorized("Invalid credentials")
        if user.status != "active":
            raise Unauthorized("Account is not active")
        if not verify_password(password, user.password_hash):
            raise Unauthorized("Invalid credentials")
        await self.repo.update_last_login(user.id)
        return user

    async def get(self, user_id: int, tenant_id: UUID) -> User:
        user = await self.repo.get_by_id(user_id, tenant_id)
        if user is None:
            raise NotFound(f"User {user_id} not found")
        return user
