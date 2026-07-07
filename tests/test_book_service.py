"""BookService 业务逻辑测试"""
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.schemas.book import BookCreate, BookUpdate
from backend.service.book_service import BookService
from models import Base


@pytest.fixture
async def service():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield BookService(session)
    await engine.dispose()


async def test_create_and_get_book(service):
    data = BookCreate(title="测试书", author="作者")
    book = await service.create_book(data)
    assert book.id is not None
    assert book.title == "测试书"

    fetched = await service.get_book(book.id)
    assert fetched is not None
    assert fetched.title == "测试书"


async def test_list_books_empty(service):
    books, total = await service.list_books()
    assert total == 0
    assert books == []


async def test_list_books_with_data(service):
    await service.create_book(BookCreate(title="书1", author="A1"))
    await service.create_book(BookCreate(title="书2", author="A2"))
    books, total = await service.list_books()
    assert total == 2
    assert len(books) == 2


async def test_list_books_search(service):
    await service.create_book(BookCreate(title="Python编程", author="张三"))
    await service.create_book(BookCreate(title="Java编程", author="李四"))
    books, total = await service.list_books(q="Python")
    assert total == 1
    assert books[0].title == "Python编程"


async def test_list_books_category_filter(service):
    await service.create_book(BookCreate(title="科幻书", author="A", category="科幻"))
    await service.create_book(BookCreate(title="文学书", author="B", category="文学"))
    books, total = await service.list_books(category="文学")
    assert total == 1
    assert books[0].category == "文学"


async def test_update_book(service):
    book = await service.create_book(BookCreate(title="旧书名", author="作者"))
    updated = await service.update_book(book.id, BookUpdate(title="新书名"))
    assert updated.title == "新书名"


async def test_delete_book(service):
    book = await service.create_book(BookCreate(title="待删除", author="作者"))
    ok = await service.delete_book(book.id)
    assert ok is True
    assert await service.get_book(book.id) is None


async def test_import_json(service):
    items = [
        BookCreate(title="导入1", author="A1"),
        BookCreate(title="导入2", author="A2"),
    ]
    result = await service.import_json(items)
    assert result["success"] == 2
    assert result["errors"] == 0
    _, total = await service.list_books()
    assert total == 2


async def test_create_book_available_exceeds_total(service):
    with pytest.raises(ValueError, match="可借数不能大于总册数"):
        await service.create_book(BookCreate(title="错误", author="A", total=1, available=5))
