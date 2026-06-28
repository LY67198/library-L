from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int, tenant_id: UUID) -> User | None:
        stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_student_no(self, student_no: str, tenant_id: UUID) -> User | None:
        stmt = select(User).where(User.student_no == student_no, User.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        tenant_id: UUID,
        student_no: str,
        password_hash: str,
        full_name: str,
        email: str | None = None,
        role: str = "student",
    ) -> User:
        user = User(
            tenant_id=tenant_id,
            student_no=student_no,
            password_hash=password_hash,
            full_name=full_name,
            email=email,
            role=role,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update_last_login(self, user_id: int) -> None:
        user = await self.session.get(User, user_id)
        if user is not None:
            user.last_login_at = datetime.now(timezone.utc)
            await self.session.flush()
