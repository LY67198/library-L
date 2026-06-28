from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Policy


class PolicyRepository:
    """馆内政策表的数据访问对象,管理政策文档的持久化与版本号自增。"""

    def __init__(self, session: AsyncSession):
        """初始化仓储实例。

        参数:
            session: SQLAlchemy 异步会话
        """
        self.session = session

    async def get_by_id(self, policy_id: int, tenant_id: UUID) -> Policy | None:
        """按主键与租户 ID 查询单条政策。

        参数:
            policy_id: 政策主键 ID
            tenant_id: 所属租户 ID

        返回值:
            Policy | None: 命中则返回政策对象,否则返回 None
        """
        stmt = select(Policy).where(Policy.id == policy_id, Policy.tenant_id == tenant_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_all(self, tenant_id: UUID) -> list[Policy]:
        """列出指定租户下的全部政策,按主键升序。

        参数:
            tenant_id: 所属租户 ID

        返回值:
            list[Policy]: 政策列表
        """
        stmt = select(Policy).where(Policy.tenant_id == tenant_id).order_by(Policy.id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def create(self, *, tenant_id: UUID, data: dict) -> Policy:
        """创建一条政策记录。

        参数:
            tenant_id: 所属租户 ID
            data: 政策字段字典

        返回值:
            Policy: 已写入数据库的政策对象
        """
        policy = Policy(tenant_id=tenant_id, **data)
        self.session.add(policy)
        await self.session.flush()
        await self.session.refresh(policy)
        return policy

    async def update(self, policy: Policy, data: dict) -> Policy:
        """更新指定政策的字段并自增版本号(只覆盖非空值)。

        参数:
            policy: 已加载的政策 ORM 实例
            data: 待更新字段字典

        返回值:
            Policy: 更新后的政策对象
        """
        for k, v in data.items():
            if v is not None:
                setattr(policy, k, v)
        policy.version += 1
        await self.session.flush()
        await self.session.refresh(policy)
        return policy

    async def delete(self, policy: Policy) -> None:
        """删除指定政策。

        参数:
            policy: 已加载的政策 ORM 实例
        """
        await self.session.delete(policy)
        await self.session.flush()