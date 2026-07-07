"""Book 模型测试"""
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models import Book, Base


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def test_create_book(db_session):
    book = Book(title="测试书", author="测试作者", total=2, available=2)
    db_session.add(book)
    await db_session.commit()
    await db_session.refresh(book)
    assert book.id is not None
    assert book.title == "测试书"
    assert book.total == 2


async def test_book_defaults(db_session):
    book = Book(title="默认值测试", author="作者")
    db_session.add(book)
    await db_session.commit()
    await db_session.refresh(book)
    assert book.total == 1
    assert book.available == 1
    assert book.isbn is None
    assert book.created_at is not None
    assert book.updated_at is not None


async def test_book_isbn_unique(db_session):
    b1 = Book(title="书1", author="作者1", isbn="9781234567890")
    b2 = Book(title="书2", author="作者2", isbn="9781234567890")
    db_session.add(b1)
    await db_session.commit()
    db_session.add(b2)
    with pytest.raises(Exception):
        await db_session.commit()
