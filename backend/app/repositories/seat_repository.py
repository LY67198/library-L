from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Seat


class SeatRepository:
    """座位表的数据访问对象,提供按楼层、租户的查询能力。"""

    def __init__(self, session: AsyncSession):
        """初始化仓储实例。

        参数:
            session: SQLAlchemy 异步会话
        """
        self.session = session

    async def get_by_id(self, seat_id: int, tenant_id: UUID) -> Seat | None:
        """按主键与租户 ID 查询单个座位。

        参数:
            seat_id: 座位主键 ID
            tenant_id: 所属租户 ID

        返回值:
            Seat | None: 命中则返回座位对象,否则返回 None
        """
        stmt = select(Seat).where(Seat.id == seat_id, Seat.tenant_id == tenant_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_all(self, tenant_id: UUID) -> list[Seat]:
        """列出指定租户下的全部座位,按楼层与编号排序。

        参数:
            tenant_id: 所属租户 ID

        返回值:
            list[Seat]: 座位列表
        """
        stmt = select(Seat).where(Seat.tenant_id == tenant_id).order_by(Seat.floor, Seat.code)
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_by_floor(self, tenant_id: UUID, floor: str) -> list[Seat]:
        """按楼层筛选座位,按编号排序。

        参数:
            tenant_id: 所属租户 ID
            floor: 楼层标识

        返回值:
            list[Seat]: 该楼层的座位列表
        """
        stmt = (
            select(Seat)
            .where(Seat.tenant_id == tenant_id, Seat.floor == floor)
            .order_by(Seat.code)
        )
        return list((await self.session.execute(stmt)).scalars().all())