"""Admin 图书管理 API 测试"""
import pytest
from httpx import ASGITransport, AsyncClient

from app_main import create_app
from core.security import create_access_token, hash_password
from models import Base, User, Book
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
        admin_user = User(
            username="admin", password_hash=hash_password("admin123"),
            display_name="Admin", student_id="ADMIN001", is_admin=True,
        )
        normal_user = User(
            username="user", password_hash=hash_password("user123"),
            display_name="User", student_id="U001", is_admin=False,
        )
        session.add_all([admin_user, normal_user])
        await session.commit()
        await session.refresh(admin_user)
        await session.refresh(normal_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, admin_user, normal_user, factory

    app.dependency_overrides.clear()
    await engine.dispose()


def _auth_header(user):
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


async def test_list_books_empty(client):
    c, admin, _, _ = client
    resp = await c.get("/api/v1/admin/books", headers=_auth_header(admin))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


async def test_create_and_list_book(client):
    c, admin, _, _ = client
    resp = await c.post("/api/v1/admin/books", json={
        "title": "测试书", "author": "作者", "total": 2, "available": 2,
    }, headers=_auth_header(admin))
    assert resp.status_code == 201
    assert resp.json()["title"] == "测试书"

    resp = await c.get("/api/v1/admin/books", headers=_auth_header(admin))
    assert resp.json()["total"] == 1


async def test_get_book_not_found(client):
    c, admin, _, _ = client
    resp = await c.get("/api/v1/admin/books/nonexistent-id", headers=_auth_header(admin))
    assert resp.status_code == 404


async def test_update_book(client):
    c, admin, _, factory = client
    async with factory() as session:
        book = Book(title="旧名", author="作者")
        session.add(book)
        await session.commit()
        await session.refresh(book)
        bid = book.id

    resp = await c.put(f"/api/v1/admin/books/{bid}", json={
        "title": "新名"
    }, headers=_auth_header(admin))
    assert resp.status_code == 200
    assert resp.json()["title"] == "新名"


async def test_delete_book(client):
    c, admin, _, factory = client
    async with factory() as session:
        book = Book(title="待删", author="作者")
        session.add(book)
        await session.commit()
        await session.refresh(book)
        bid = book.id

    resp = await c.delete(f"/api/v1/admin/books/{bid}", headers=_auth_header(admin))
    assert resp.status_code == 204


async def test_non_admin_denied(client):
    c, _, normal, _ = client
    resp = await c.post("/api/v1/admin/books", json={
        "title": "测试", "author": "作者",
    }, headers=_auth_header(normal))
    assert resp.status_code == 403


async def test_unauthorized_no_token(client):
    c, _, _, _ = client
    resp = await c.get("/api/v1/admin/books")
    assert resp.status_code == 401


async def test_import_json(client):
    c, admin, _, _ = client
    resp = await c.post("/api/v1/admin/books/import", json={
        "items": [
            {"title": "导入1", "author": "A1"},
            {"title": "导入2", "author": "A2"},
        ]
    }, headers=_auth_header(admin))
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] == 2


async def test_search_books(client):
    c, admin, _, factory = client
    async with factory() as session:
        session.add(Book(title="Python程序设计", author="张三"))
        session.add(Book(title="Java核心技术", author="李四"))
        await session.commit()

    resp = await c.get("/api/v1/admin/books?q=Python", headers=_auth_header(admin))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Python程序设计"
