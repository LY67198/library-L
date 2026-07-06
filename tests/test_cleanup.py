"""测试座位预约超时清理逻辑"""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from core.cleanup import cleanup_expired_slots, _slot_cutoff
from core.lock import SeatLock
from models import Appointment, AppointmentStatus, Seat, SeatStatus, SeatTimeSlot, TimeSlot, User


def make_user() -> User:
    return User(
        id="u1",
        username="testuser",
        password_hash="hash",
        display_name="Test",
        student_id="S001",
    )


def make_seat(id: str = "s1") -> Seat:
    return Seat(
        id=id,
        zone_id=1,
        seat_number="001",
        status=SeatStatus.available,
    )


def make_sts(seat_id: str, date_val: date, slot: str, user_id: str, booked_at_override=None):
    """创建 SeatTimeSlot 测试数据"""
    booked_at = booked_at_override or datetime.now(timezone.utc)
    return SeatTimeSlot(
        id=f"sts-{seat_id}-{slot}",
        seat_id=seat_id,
        date=date_val,
        slot=TimeSlot(slot),
        user_id=user_id,
        booked_at=booked_at,
    )


def make_appt(id: str, user_id: str, seat_id: str, date_val: date, slot: str):
    """创建 Appointment 测试数据"""
    return Appointment(
        id=id,
        user_id=user_id,
        seat_id=seat_id,
        date=date_val,
        slot=TimeSlot(slot),
        status=AppointmentStatus.booked,
    )


class TestSlotCutoff:
    """_slot_cutoff 工具函数测试"""

    def test_morning_cutoff(self):
        d = date(2026, 7, 6)
        cutoff = _slot_cutoff(d, "morning")
        assert cutoff.hour == 0
        assert cutoff.minute == 30

    def test_afternoon_cutoff(self):
        d = date(2026, 7, 6)
        cutoff = _slot_cutoff(d, "afternoon")
        assert cutoff.hour == 5
        assert cutoff.minute == 30

    def test_evening_cutoff(self):
        d = date(2026, 7, 6)
        cutoff = _slot_cutoff(d, "evening")
        assert cutoff.hour == 10
        assert cutoff.minute == 30


class TestCleanupExpiredSlots:
    """cleanup_expired_slots 核心逻辑测试"""

    @pytest.mark.asyncio
    async def test_empty_table_returns_zero(self, db_session, redis_client):
        lock = SeatLock(redis_client)
        today = date.today()
        count = await cleanup_expired_slots(db_session, lock, today)
        assert count == 0

    @pytest.mark.asyncio
    async def test_expired_slot_is_cleaned(self, db_session, redis_client):
        """过期时段被清理，Appointment 标记为 expired"""
        lock = SeatLock(redis_client)
        today = date.today()

        user = make_user()
        seat = make_seat()
        db_session.add_all([user, seat])
        await db_session.flush()

        # 过去的时间（模拟已过期）
        old_time = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
        sts = make_sts(seat.id, today, "morning", user.id, booked_at_override=old_time)
        appt = make_appt("a1", user.id, seat.id, today, "morning")
        db_session.add_all([sts, appt])
        await db_session.commit()

        count = await cleanup_expired_slots(db_session, lock, today)
        assert count == 1

        # 验证 SeatTimeSlot 已删除
        sts_check = await db_session.execute(
            select(SeatTimeSlot).where(SeatTimeSlot.seat_id == seat.id)
        )
        assert sts_check.scalar_one_or_none() is None

        # 验证 Appointment 状态变为 expired
        await db_session.refresh(appt)
        assert appt.status == AppointmentStatus.expired

    @pytest.mark.asyncio
    async def test_future_slot_not_cleaned(self, db_session, redis_client):
        """未过期时段不被清理"""
        lock = SeatLock(redis_client)
        today = date.today()

        user = make_user()
        seat = make_seat()
        db_session.add_all([user, seat])
        await db_session.flush()

        sts = make_sts(seat.id, today, "morning", user.id)
        appt = make_appt("a1", user.id, seat.id, today, "morning")
        db_session.add_all([sts, appt])
        await db_session.commit()

        count = await cleanup_expired_slots(db_session, lock, today)
        assert count == 0

        sts_check = await db_session.execute(
            select(SeatTimeSlot).where(SeatTimeSlot.seat_id == seat.id)
        )
        assert sts_check.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_tomorrow_slot_not_cleaned(self, db_session, redis_client):
        """明天的预约不被清理"""
        lock = SeatLock(redis_client)
        today = date.today()
        # safely compute tomorrow
        tomorrow = today.replace(day=min(today.day + 1, 28))

        user = make_user()
        seat = make_seat()
        db_session.add_all([user, seat])
        await db_session.flush()

        old_time = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
        sts = make_sts(seat.id, tomorrow, "morning", user.id, booked_at_override=old_time)
        appt = make_appt("a1", user.id, seat.id, tomorrow, "morning")
        db_session.add_all([sts, appt])
        await db_session.commit()

        # 清理 today，不应影响 tomorrow
        count = await cleanup_expired_slots(db_session, lock, today)
        assert count == 0

        # tomorrow 的记录还在
        sts_check = await db_session.execute(
            select(SeatTimeSlot).where(SeatTimeSlot.seat_id == seat.id)
        )
        assert sts_check.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_mixed_slots_expired_and_fresh(self, db_session, redis_client):
        """过期+未过期的混合场景，只删过期的"""
        lock = SeatLock(redis_client)
        today = date.today()

        user = make_user()
        seat = make_seat()
        db_session.add_all([user, seat])
        await db_session.flush()

        old_time = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)

        # 过期
        sts1 = make_sts(seat.id, today, "morning", user.id, booked_at_override=old_time)
        appt1 = make_appt("a1", user.id, seat.id, today, "morning")
        # 未过期
        sts2 = make_sts(seat.id, today, "afternoon", user.id)
        appt2 = make_appt("a2", user.id, seat.id, today, "afternoon")
        db_session.add_all([sts1, appt1, sts2, appt2])
        await db_session.commit()

        count = await cleanup_expired_slots(db_session, lock, today)
        assert count == 1

        # morning 被删，afternoon 保留
        all_sts = (await db_session.execute(select(SeatTimeSlot))).scalars().all()
        assert len(all_sts) == 1
        assert all_sts[0].slot == TimeSlot.afternoon

    @pytest.mark.asyncio
    async def test_redis_lock_released_on_cleanup(self, db_session, redis_client):
        """过期清理时 Redis key 被释放"""
        lock = SeatLock(redis_client)
        today = date.today()
        date_str = str(today)

        user = make_user()
        seat = make_seat()
        db_session.add_all([user, seat])
        await db_session.flush()

        # 先设置 Redis 锁
        await lock.acquire(seat.id, date_str, "morning", user.id, ttl=300)
        assert await lock.is_locked(seat.id, date_str, "morning") is True

        old_time = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
        sts = make_sts(seat.id, today, "morning", user.id, booked_at_override=old_time)
        appt = make_appt("a1", user.id, seat.id, today, "morning")
        db_session.add_all([sts, appt])
        await db_session.commit()

        await cleanup_expired_slots(db_session, lock, today)

        # Redis key 应被释放
        assert await lock.is_locked(seat.id, date_str, "morning") is False

    @pytest.mark.asyncio
    async def test_specific_slot_cleans_only_that_slot(self, db_session, redis_client):
        """slot='morning' 时只清理 morning，不影响其他时段"""
        lock = SeatLock(redis_client)
        today = date.today()

        user = make_user()
        seat = make_seat()
        db_session.add_all([user, seat])
        await db_session.flush()

        old_time = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)

        sts1 = make_sts(seat.id, today, "morning", user.id, booked_at_override=old_time)
        appt1 = make_appt("a1", user.id, seat.id, today, "morning")
        sts2 = make_sts(seat.id, today, "evening", user.id, booked_at_override=old_time)
        appt2 = make_appt("a2", user.id, seat.id, today, "evening")
        db_session.add_all([sts1, appt1, sts2, appt2])
        await db_session.commit()

        # 只清理 morning
        count = await cleanup_expired_slots(db_session, lock, today, slot="morning")
        assert count == 1

        all_sts = (await db_session.execute(select(SeatTimeSlot))).scalars().all()
        assert len(all_sts) == 1
        assert all_sts[0].slot == TimeSlot.evening
