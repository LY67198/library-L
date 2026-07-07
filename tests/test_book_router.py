"""公开图书搜索 API 测试"""
import pytest
from httpx import ASGITransport, AsyncClient

from app_main import create_app
from models import Base, Book
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from core.database import get_db


@pytest.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _get_db():
        async with factory() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_db] = _get_db

    async with factory() as session:
        session.add_all([
            Book(title="Python编程", author="张三", category="计算机"),
            Book(title="百年孤独", author="马尔克斯", category="文学"),
        ])
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    await engine.dispose()


async def test_search_books_no_query(client):
    resp = await client.get("/api/v1/books")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] == 2


async def test_search_books_by_title(client):
    resp = await client.get("/api/v1/books?q=Python")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Python编程"


async def test_search_books_by_category(client):
    resp = await client.get("/api/v1/books?category=文学")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "百年孤独"


async def test_search_books_pagination(client):
    resp = await client.get("/api/v1/books?offset=0&limit=1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["total"] == 2
