"""Auth API 集成测试 — 注册 → 登录 → refresh → me"""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_register_success(db_session):
    """注册成功返回 201 和用户信息"""
    from core.database import get_db

    async def override_get_db():
        yield db_session

    from app_main import app

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/register", json={
            "username": "testuser1",
            "password": "password123",
            "display_name": "测试用户",
            "student_id": "2024001",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "testuser1"
        assert "user_id" in data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_register_duplicate_username(db_session):
    """重复用户名注册返回 409"""
    from core.database import get_db

    async def override_get_db():
        yield db_session

    from app_main import app

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/v1/auth/register", json={
            "username": "dupuser",
            "password": "password123",
            "display_name": "重复用户",
            "student_id": "2024101",
        })
        resp = await client.post("/api/v1/auth/register", json={
            "username": "dupuser",
            "password": "password456",
            "display_name": "重复用户2",
            "student_id": "2024102",
        })
        assert resp.status_code == 409

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_success(db_session):
    """登录成功返回 access_token + refresh_token"""
    from core.database import get_db

    async def override_get_db():
        yield db_session

    from app_main import app

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/v1/auth/register", json={
            "username": "loginuser",
            "password": "mypassword",
            "display_name": "登录用户",
            "student_id": "2024201",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "username": "loginuser",
            "password": "mypassword",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_wrong_password(db_session):
    """错误密码登录返回 401"""
    from core.database import get_db

    async def override_get_db():
        yield db_session

    from app_main import app

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/v1/auth/register", json={
            "username": "wrongpw",
            "password": "correct",
            "display_name": "错误密码测试",
            "student_id": "2024301",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "username": "wrongpw",
            "password": "incorrect",
        })
        assert resp.status_code == 401

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_refresh_token_flow(db_session):
    """refresh_token 换取 access_token"""
    from core.database import get_db

    async def override_get_db():
        yield db_session

    from app_main import app

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/v1/auth/register", json={
            "username": "refreshuser",
            "password": "testpass123",
            "display_name": "刷新测试",
            "student_id": "2024401",
        })
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": "refreshuser", "password": "testpass123",
        })
        refresh_token = login_resp.json()["refresh_token"]

        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_me_endpoint(db_session):
    """/me 返回当前用户信息，无 token 返回 401"""
    from core.database import get_db

    async def override_get_db():
        yield db_session

    from app_main import app

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/v1/auth/register", json={
            "username": "meuser",
            "password": "testpass123",
            "display_name": "Me测试",
            "student_id": "2024501",
        })
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": "meuser", "password": "testpass123",
        })
        access_token = login_resp.json()["access_token"]

        resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "meuser"
        assert data["display_name"] == "Me测试"

        resp2 = await client.get("/api/v1/auth/me")
        assert resp2.status_code == 401

    app.dependency_overrides.clear()
