from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Appointment, AppointmentStatus


class AppointmentRepository:
    """预约表的数据访问对象,提供冲突检测与乐观锁更新能力。"""

    def __init__(self, session: AsyncSession):
        """初始化仓储实例。

        参数:
            session: SQLAlchemy 异步会话
        """
        self.session = session

    async def list_for_user(self, user_id: int, tenant_id: UUID) -> list[Appointment]:
        """列出指定用户的所有预约,按开始时间倒序。

        参数:
            user_id: 用户主键 ID
            tenant_id: 所属租户 ID

        返回值:
            list[Appointment]: 该用户的预约列表
        """
        stmt = (
            select(Appointment)
            .where(Appointment.user_id == user_id, Appointment.tenant_id == tenant_id)
            .order_by(Appointment.start_time.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_id(self, appt_id: int, tenant_id: UUID) -> Appointment | None:
        """按主键与租户 ID 查询单个预约。

        参数:
            appt_id: 预约主键 ID
            tenant_id: 所属租户 ID

        返回值:
            Appointment | None: 命中则返回预约对象,否则返回 None
        """
        stmt = select(Appointment).where(
            Appointment.id == appt_id, Appointment.tenant_id == tenant_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def check_time_conflict(
        self,
        tenant_id: UUID,
        seat_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> bool:
        """检测指定座位在给定时间段内是否存在未取消的预约冲突。

        参数:
            tenant_id: 所属租户 ID
            seat_id: 座位主键 ID
            start_time: 待预约的开始时间
            end_time: 待预约的结束时间

        返回值:
            bool: 若存在冲突则返回 True,否则返回 False
        """
        stmt = select(Appointment.id).where(
            and_(
                Appointment.tenant_id == tenant_id,
                Appointment.seat_id == seat_id,
                Appointment.status.in_(
                    [AppointmentStatus.pending.value, AppointmentStatus.confirmed.value, AppointmentStatus.active.value]
                ),
                Appointment.start_time < end_time,
                Appointment.end_time > start_time,
            )
        ).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def create(
        self,
        *,
        tenant_id: UUID,
        user_id: int,
        seat_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> Appointment:
        """创建一条预约记录,初始状态为 confirmed,乐观锁版本从 0 起。

        参数:
            tenant_id: 所属租户 ID
            user_id: 预约用户主键 ID
            seat_id: 座位主键 ID
            start_time: 开始时间
            end_time: 结束时间

        返回值:
            Appointment: 已写入数据库的预约对象
        """
        appt = Appointment(
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type="seat",
            resource_id=seat_id,
            seat_id=seat_id,
            start_time=start_time,
            end_time=end_time,
            status=AppointmentStatus.confirmed.value,
            version=0,
        )
        self.session.add(appt)
        await self.session.flush()
        await self.session.refresh(appt)
        return appt

    async def cancel_with_version(
        self,
        appt: Appointment,
        *,
        expected_version: int,
        reason: str | None = None,
    ) -> bool:
        """基于乐观锁(version)的取消操作。

        仅当数据库中该预约的当前 version 与 expected_version 一致时才会更新成功,
        否则 rowcount 为 0,视为并发冲突并由调用方决定重试。

        参数:
            appt: 已加载的预约 ORM 实例
            expected_version: 调用方读取时的乐观锁版本号
            reason: 取消原因(可选)

        返回值:
            bool: 更新成功返回 True,版本号不匹配返回 False
        """
        now = datetime.utcnow()
        stmt = (
            update(Appointment)
            .where(Appointment.id == appt.id, Appointment.version == expected_version)
            .values(
                status=AppointmentStatus.cancelled.value,
                cancelled_at=now,
                cancel_reason=reason,
                version=expected_version + 1,
            )
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0