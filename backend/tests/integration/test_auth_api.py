"""认证 API 集成测试 — 验证 register / login / me 的成功、冲突、校验失败与未鉴权场景。"""
from __future__ import annotations

from uuid import UUID

import pytest

pytestmark = pytest.mark.integration


async def _seed_default_tenant(db_session):
    """辅助函数:确保默认 tenant 记录存在,auth 相关测试统一通过该 fixture 初始化。"""
    from app.models import Tenant

    existing = await db_session.get(Tenant, UUID("00000000-0000-0000-0000-000000000001"))
    if existing:
        return existing
    tenant = Tenant(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        code="main_library",
        name="Main Library",
        status="active",
        config={},
    )
    db_session.add(tenant)
    await db_session.commit()
    return tenant


async def test_register_new_user_returns_tokens(client, db_session):
    """测试新用户注册:返回 201,bearer token、access/refresh token 与 user 字段,且角色默认为 student。"""
    await _seed_default_tenant(db_session)
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "student_no": "2024001",
            "password": "strong_password_123",
            "full_name": "Test Student",
            "email": "test@example.com",
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 3600
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["student_no"] == "2024001"
    assert data["user"]["role"] == "student"


async def test_register_duplicate_student_no_conflict(client, db_session):
    """测试重复学号注册:首次返回 201,再次用相同学号注册应返回 409 conflict。"""
    await _seed_default_tenant(db_session)
    payload = {
        "student_no": "2024002",
        "password": "strong_password_123",
        "full_name": "Test Student",
    }
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


async def test_register_validation_error_short_password(client, db_session):
    """测试短密码注册:服务端应返回 422 validation_error,防止弱密码。"""
    await _seed_default_tenant(db_session)
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "student_no": "2024003",
            "password": "short",
            "full_name": "Test",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_login_success(client, db_session):
    """测试登录成功:用注册时的 student_no + 正确密码登录,返回 200 和 access_token。"""
    await _seed_default_tenant(db_session)
    await client.post(
        "/api/v1/auth/register",
        json={
            "student_no": "2024010",
            "password": "login_test_pwd",
            "full_name": "Login Test",
        },
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"student_no": "2024010", "password": "login_test_pwd"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


async def test_login_wrong_password_returns_401(client, db_session):
    """测试错误密码登录:应返回 401 unauthorized,错误码 unauthorized。"""
    await _seed_default_tenant(db_session)
    await client.post(
        "/api/v1/auth/register",
        json={
            "student_no": "2024011",
            "password": "correct_password",
            "full_name": "Wrong Pwd Test",
        },
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"student_no": "2024011", "password": "wrong_password"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_me_returns_current_user(client, db_session):
    """测试 /auth/me:携带 access token 应返回当前用户信息,角色为 student。"""
    await _seed_default_tenant(db_session)
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "student_no": "2024020",
            "password": "me_test_pwd",
            "full_name": "Me Test",
        },
    )
    token = reg.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["student_no"] == "2024020"
    assert data["roles"] == ["student"]


async def test_me_without_token_returns_401(client):
    """测试 /auth/me 未鉴权:无 token 应返回 401 unauthorized,拦截未登录访问。"""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
