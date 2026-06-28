from uuid import UUID

import pytest

pytestmark = pytest.mark.integration


async def _seed_default_tenant(db_session):
    """Helper: ensure the default tenant exists for auth tests."""
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
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
