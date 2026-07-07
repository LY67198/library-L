"""ProfileService 单元测试"""
import pytest
from datetime import datetime, timezone
from backend.service.profile_service import ProfileService
from models import (
    User, Book, BorrowRecord, BorrowStatus, Appointment, AppointmentStatus,
    Floor, Zone, Seat, SeatTimeSlot, TimeSlot,
)


@pytest.mark.asyncio
async def test_get_profile_user_only(db_session):
    """测试仅查询用户信息"""
    user = User(
        username="reader1",
        password_hash="hash",
        display_name="读者一号",
        student_id="R001",
    )
    db_session.add(user)
    await db_session.commit()

    service = ProfileService(db_session)
    result = await service.get_profile(user.id, "personal_info")

    assert result["user"] is not None
    assert result["user"].display_name == "读者一号"
    assert result["user"].student_id == "R001"
    assert result["appointments"] == []
    assert result["borrow_records"] == []


@pytest.mark.asyncio
async def test_get_profile_with_appointments(db_session):
    """测试查询用户信息 + 预约记录"""
    user = User(
        username="reader2",
        password_hash="hash",
        display_name="读者二号",
        student_id="R002",
    )
    floor = Floor(name="1F", sort_order=1)
    db_session.add(floor)
    await db_session.flush()

    zone = Zone(floor_id=floor.id, name="自习区", zone_type="open", sort_order=1)
    db_session.add(zone)
    await db_session.flush()

    seat = Seat(zone_id=zone.id, seat_number="A01")

    db_session.add_all([user, seat])
    await db_session.flush()

    slot = SeatTimeSlot(
        seat_id=seat.id,
        date=datetime(2026, 7, 8).date(),
        slot=TimeSlot.morning,
        user_id=user.id,
    )
    appt = Appointment(
        user_id=user.id,
        seat_id=seat.id,
        date=datetime(2026, 7, 8).date(),
        slot=TimeSlot.morning,
        status=AppointmentStatus.booked,
    )
    db_session.add_all([slot, appt])
    await db_session.commit()

    service = ProfileService(db_session)
    result = await service.get_profile(user.id, "all")

    assert result["user"].display_name == "读者二号"
    assert len(result["appointments"]) == 1
    assert result["appointments"][0].status == AppointmentStatus.booked


@pytest.mark.asyncio
async def test_get_profile_with_borrow_history(db_session):
    """测试查询借阅记录"""
    user = User(
        username="reader3",
        password_hash="hash",
        display_name="读者三号",
        student_id="R003",
    )
    book = Book(
        title="百年孤独",
        author="加西亚·马尔克斯",
        total=2,
        available=1,
    )
    db_session.add_all([user, book])
    await db_session.commit()

    record = BorrowRecord(
        user_id=user.id,
        book_id=book.id,
        due_at=datetime(2026, 8, 7, tzinfo=timezone.utc),
        status=BorrowStatus.borrowed,
    )
    db_session.add(record)
    await db_session.commit()

    service = ProfileService(db_session)
    result = await service.get_profile(user.id, "borrowing_history")

    assert result["user"].display_name == "读者三号"
    assert len(result["borrow_records"]) == 1
    assert result["borrow_records"][0].book.title == "百年孤独"
    assert result["borrow_records"][0].status == BorrowStatus.borrowed
    assert result["appointments"] == []


@pytest.mark.asyncio
async def test_get_profile_nonexistent_user(db_session):
    """测试查询不存在的用户"""
    service = ProfileService(db_session)
    result = await service.get_profile("nonexistent-id", "all")

    assert result["user"] is None
    assert result["appointments"] == []
    assert result["borrow_records"] == []


@pytest.mark.asyncio
async def test_get_profile_empty_history(db_session):
    """测试查询没有借阅记录的用户"""
    user = User(
        username="reader5",
        password_hash="hash",
        display_name="读者五号",
        student_id="R005",
    )
    db_session.add(user)
    await db_session.commit()

    service = ProfileService(db_session)
    result = await service.get_profile(user.id, "all")

    assert result["user"].display_name == "读者五号"
    assert result["appointments"] == []
    assert result["borrow_records"] == []
