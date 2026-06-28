"""用户领域服务 — 注册、登录认证、查询等业务编排。"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, NotFound, Unauthorized
from app.core.security import hash_password, verify_password
from app.models import User
from app.repositories.user_repository import UserRepository


class UserService:
    """用户领域服务,负责注册、登录认证、查询等业务编排。"""

    def __init__(self, session: AsyncSession):
        """初始化服务实例。

        参数:
            session: SQLAlchemy 异步会话
        """
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
        """注册一个新用户,学号冲突时抛出 Conflict。

        参数:
            tenant_id: 所属租户 ID
            student_no: 学号
            password: 明文密码(将自动加盐哈希)
            full_name: 用户全名
            email: 邮箱地址(可选)
            role: 角色,默认 student

        返回值:
            User: 新创建的用户对象

        抛出:
            Conflict: 学号在该租户内已存在
        """
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
        """使用学号与密码进行登录认证,成功后更新最近登录时间。

        参数:
            tenant_id: 所属租户 ID
            student_no: 学号
            password: 明文密码

        返回值:
            User: 认证通过的用户对象

        抛出:
            Unauthorized: 学号不存在、账户未激活或密码错误
        """
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
        """按主键与租户 ID 查询用户。

        参数:
            user_id: 用户主键 ID
            tenant_id: 所属租户 ID

        返回值:
            User: 用户对象

        抛出:
            NotFound: 用户不存在
        """
        user = await self.repo.get_by_id(user_id, tenant_id)
        if user is None:
            raise NotFound(f"User {user_id} not found")
        return user