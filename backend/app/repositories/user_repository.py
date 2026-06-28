from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    """用户表的数据访问对象,所有方法强制携带 tenant_id 以实现多租户隔离。"""

    def __init__(self, session: AsyncSession):
        """初始化仓储实例。

        参数:
            session: SQLAlchemy 异步会话
        """
        self.session = session

    async def get_by_id(self, user_id: int, tenant_id: UUID) -> User | None:
        """按主键与租户 ID 查询单个用户。

        参数:
            user_id: 用户主键 ID
            tenant_id: 所属租户 ID

        返回值:
            User | None: 命中则返回用户对象,否则返回 None
        """
        stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_student_no(self, student_no: str, tenant_id: UUID) -> User | None:
        """按学号与租户 ID 查询单个用户。

        参数:
            student_no: 学号(租户内唯一)
            tenant_id: 所属租户 ID

        返回值:
            User | None: 命中则返回用户对象,否则返回 None
        """
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
        """创建一条用户记录。

        参数:
            tenant_id: 所属租户 ID
            student_no: 学号
            password_hash: 已加盐哈希后的密码
            full_name: 用户全名
            email: 邮箱地址(可选)
            role: 角色,默认为 student

        返回值:
            User: 已写入数据库的用户对象
        """
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
        """更新用户的最近一次登录时间。

        参数:
            user_id: 用户主键 ID
        """
        user = await self.session.get(User, user_id)
        if user is not None:
            user.last_login_at = datetime.now(timezone.utc)
            await self.session.flush()