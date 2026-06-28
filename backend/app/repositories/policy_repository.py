from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Policy


class PolicyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, policy_id: int, tenant_id: UUID) -> Policy | None:
        stmt = select(Policy).where(Policy.id == policy_id, Policy.tenant_id == tenant_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_all(self, tenant_id: UUID) -> list[Policy]:
        stmt = select(Policy).where(Policy.tenant_id == tenant_id).order_by(Policy.id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def create(self, *, tenant_id: UUID, data: dict) -> Policy:
        policy = Policy(tenant_id=tenant_id, **data)
        self.session.add(policy)
        await self.session.flush()
        await self.session.refresh(policy)
        return policy

    async def update(self, policy: Policy, data: dict) -> Policy:
        for k, v in data.items():
            if v is not None:
                setattr(policy, k, v)
        policy.version += 1
        await self.session.flush()
        await self.session.refresh(policy)
        return policy

    async def delete(self, policy: Policy) -> None:
        await self.session.delete(policy)
        await self.session.flush()