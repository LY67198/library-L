"""预约领域服务 — 业务编排,实现 Redis 锁 + PG 乐观锁的两层并发防御。"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.redis_client import get_redis
from app.core.concurrency import DistributedLock, LockAcquireError, acquire_with_retry
from app.core.exceptions import Conflict, NotFound
from app.models import Appointment
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.seat_repository import SeatRepository


class AppointmentService:
    """预约领域服务,采用「Redis 分布式锁 + PostgreSQL 乐观锁」两层并发防御策略。

    两层防御分工:
        - 第一层(Redis 分布式锁):针对同一座位/同一预约做粗粒度互斥,把绝大多数
          并发请求在进入数据库之前直接短路,降低 DB 压力,体现性能。
        - 第二层(PostgreSQL 乐观锁):对预约记录的 version 字段做条件 UPDATE,
          即使 Redis 锁因过期或网络分区失效,DB 也能保证不会出现重复预约或
          脏取消,体现正确性。

    任意一层失败都应让调用方重试或放弃,以保证最终一致性。
    """

    def __init__(self, session: AsyncSession):
        """初始化服务实例。

        参数:
            session: SQLAlchemy 异步会话
        """
        self.session = session
        self.repo = AppointmentRepository(session)
        self.seat_repo = SeatRepository(session)

    async def list_for_user(self, user_id: int, tenant_id: UUID) -> list[Appointment]:
        """列出指定用户的所有预约。

        参数:
            user_id: 用户主键 ID
            tenant_id: 所属租户 ID

        返回值:
            list[Appointment]: 预约列表,按开始时间倒序
        """
        return await self.repo.list_for_user(user_id, tenant_id)

    async def get(self, appt_id: int, tenant_id: UUID) -> Appointment:
        """按主键与租户查询预约。

        参数:
            appt_id: 预约主键 ID
            tenant_id: 所属租户 ID

        返回值:
            Appointment: 预约对象

        抛出:
            NotFound: 预约不存在
        """
        appt = await self.repo.get_by_id(appt_id, tenant_id)
        if appt is None:
            raise NotFound(f"Appointment {appt_id} not found")
        return appt

    async def book_seat(
        self,
        *,
        tenant_id: UUID,
        user_id: int,
        seat_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> Appointment:
        """为用户预订座位,执行「Redis 分布式锁 + DB 冲突检测」两层防御。

        流程:
            1. 校验座位存在与时间合法性;
            2. 获取 Redis 锁(失败时按重试策略重试,仍失败则报错让用户重试);
            3. 在锁内做数据库级时间冲突检查,确保无重叠预约;
            4. 创建预约记录;
            5. finally 中释放 Redis 锁。

        参数:
            tenant_id: 所属租户 ID
            user_id: 用户主键 ID
            seat_id: 座位主键 ID
            start_time: 开始时间
            end_time: 结束时间

        返回值:
            Appointment: 新创建的预约对象

        抛出:
            NotFound: 座位不存在
            Conflict: 时间非法、Redis 锁获取失败或时段冲突
        """
        # 校验座位存在
        seat = await self.seat_repo.get_by_id(seat_id, tenant_id)
        if seat is None:
            raise NotFound(f"Seat {seat_id} not found")
        if end_time <= start_time:
            raise Conflict("end_time must be after start_time")

        # 第一层防御:对同一座位加 Redis 分布式锁(性能层)
        redis = get_redis()
        lock_key = f"lock:seat:{tenant_id}:{seat_id}"
        try:
            lock = await acquire_with_retry(
                lambda: DistributedLock(redis, key=lock_key, ttl_ms=3000),
                max_retries=3,
            )
        except LockAcquireError:
            raise Conflict("Seat is being booked by another user, please retry")

        try:
            # 第二层防御:数据库级时间冲突检测(正确性兜底)
            conflict = await self.repo.check_time_conflict(
                tenant_id, seat_id, start_time, end_time
            )
            if conflict:
                raise Conflict("Seat is already booked in this time slot")
            return await self.repo.create(
                tenant_id=tenant_id,
                user_id=user_id,
                seat_id=seat_id,
                start_time=start_time,
                end_time=end_time,
            )
        finally:
            await lock.__aexit__(None, None, None)

    async def cancel(
        self,
        appt_id: int,
        tenant_id: UUID,
        user_id: int,
        *,
        reason: str | None = None,
    ) -> Appointment:
        """取消预约,执行「Redis 分布式锁 + PG 乐观锁」两层防御。

        流程:
            1. 校验预约存在且属于当前用户;
            2. 获取 Redis 锁(失败时报错让用户重试);
            3. 在锁内基于 version 字段做条件 UPDATE,version 不一致视为并发冲突;
            4. 刷新 ORM 状态后返回最新对象;
            5. finally 中释放 Redis 锁。

        参数:
            appt_id: 预约主键 ID
            tenant_id: 所属租户 ID
            user_id: 当前操作用户主键 ID
            reason: 取消原因(可选)

        返回值:
            Appointment: 取消后的最新预约对象

        抛出:
            NotFound: 预约不存在
            Conflict: 取消他人预约、Redis 锁获取失败或乐观锁版本冲突
        """
        appt = await self.get(appt_id, tenant_id)
        if appt.user_id != user_id:
            raise Conflict("Cannot cancel another user's appointment")
        # 第一层防御:对同一预约加 Redis 分布式锁
        redis = get_redis()
        lock_key = f"lock:appt:{tenant_id}:{appt_id}"
        try:
            lock = await acquire_with_retry(
                lambda: DistributedLock(redis, key=lock_key, ttl_ms=3000),
                max_retries=3,
            )
        except LockAcquireError:
            raise Conflict("Appointment is being modified, please retry")
        try:
            # 第二层防御:PostgreSQL 乐观锁,按 version 条件 UPDATE
            ok = await self.repo.cancel_with_version(
                appt, expected_version=appt.version, reason=reason
            )
            if not ok:
                raise Conflict("Appointment was modified concurrently, please retry")
            await self.session.refresh(appt)
            return appt
        finally:
            await lock.__aexit__(None, None, None)