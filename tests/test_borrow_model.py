"""BorrowRecord 模型单元测试"""
import pytest
from datetime import datetime, timezone
from models import (
    BorrowRecord, BorrowStatus, User, Book, Base,
)


@pytest.mark.asyncio
async def test_create_borrow_record(db_session):
    """测试创建借阅记录"""
    # 创建依赖数据
    user = User(
        username="testuser",
        password_hash="hash",
        display_name="测试用户",
        student_id="S001",
    )
    book = Book(
        title="测试图书",
        author="测试作者",
        total=3,
        available=2,
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
    await db_session.refresh(record)

    assert record.id is not None
    assert record.status == BorrowStatus.borrowed
    assert record.user_id == user.id
    assert record.book_id == book.id
    assert record.borrowed_at is not None
    assert record.returned_at is None


@pytest.mark.asyncio
async def test_borrow_record_relationship(db_session):
    """测试关联关系 loading"""
    user = User(
        username="testuser2",
        password_hash="hash",
        display_name="测试用户2",
        student_id="S002",
    )
    book = Book(
        title="测试图书2",
        author="测试作者2",
        total=1,
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
    await db_session.refresh(record, ["user", "book"])

    assert record.user.username == "testuser2"
    assert record.book.title == "测试图书2"


@pytest.mark.asyncio
async def test_borrow_record_status_transition(db_session):
    """测试借阅状态转换"""
    user = User(
        username="testuser3",
        password_hash="hash",
        display_name="测试用户3",
        student_id="S003",
    )
    book = Book(
        title="测试图书3",
        author="测试作者3",
        total=1,
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

    # borrowed -> returned
    record.status = BorrowStatus.returned
    record.returned_at = datetime.now(timezone.utc)
    await db_session.commit()
    await db_session.refresh(record)

    assert record.status == BorrowStatus.returned
    assert record.returned_at is not None

    # returned -> overdue
    record.status = BorrowStatus.overdue
    record.returned_at = None
    await db_session.commit()
    await db_session.refresh(record)

    assert record.status == BorrowStatus.overdue
    assert record.returned_at is None


@pytest.mark.asyncio
async def test_borrow_record_fk_constraint(db_session):
    """测试 user_id 外键约束"""
    book = Book(
        title="测试图书4",
        author="测试作者4",
        total=1,
        available=1,
    )
    db_session.add(book)
    await db_session.commit()

    record = BorrowRecord(
        user_id="nonexistent-uuid",
        book_id=book.id,
        due_at=datetime(2026, 8, 7, tzinfo=timezone.utc),
    )
    db_session.add(record)
    with pytest.raises(Exception):
        await db_session.commit()
