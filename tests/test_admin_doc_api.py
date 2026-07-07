"""Admin 文档管理 API 测试"""
import pytest
from httpx import ASGITransport, AsyncClient

from app_main import create_app
from core.security import create_access_token, hash_password
from models import Base, User
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
        session.add(admin_user)
        await session.commit()
        await session.refresh(admin_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, admin_user

    app.dependency_overrides.clear()
    await engine.dispose()


def _auth_header(user):
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


async def test_list_docs_empty(client):
    c, admin = client
    resp = await c.get("/api/v1/admin/documents", headers=_auth_header(admin))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


async def test_delete_nonexistent_doc(client):
    c, admin = client
    resp = await c.delete("/api/v1/admin/documents/nonexistent", headers=_auth_header(admin))
    assert resp.status_code == 404


async def test_unauthorized_no_token(client):
    c, _ = client
    resp = await c.get("/api/v1/admin/documents")
    assert resp.status_code == 401
