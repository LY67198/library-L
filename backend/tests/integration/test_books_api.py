"""图书 API 集成测试 — 验证空列表、student 角色无权创建、librarian 创建并可被列出。"""
from uuid import UUID

import pytest

pytestmark = pytest.mark.integration


async def _seed_tenant(db_session):
    """辅助函数:确保默认 tenant 存在,books 测试统一使用。"""
    from app.models import Tenant
    tid = UUID("00000000-0000-0000-0000-000000000001")
    existing = await db_session.get(Tenant, tid)
    if not existing:
        tenant = Tenant(id=tid, code="main_library", name="Main Library", status="active", config={})
        db_session.add(tenant)
        await db_session.commit()
    return tid


async def _register_user(client, student_no="2024001"):
    """辅助函数:注册一个用户并返回其 access_token,方便后续带 Bearer 头调用。"""
    response = await client.post(
        "/api/v1/auth/register",
        json={"student_no": student_no, "password": "test_pass_123", "full_name": "Test"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


async def test_list_books_empty(client, db_session):
    """测试空列表场景:注册后调用 /books 应返回 200,items=[] 且 total=0。"""
    await _seed_tenant(db_session)
    token = await _register_user(client)
    response = await client.get("/api/v1/books", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_create_book_requires_librarian(client, db_session):
    """测试角色权限:student 角色尝试创建图书应返回 403,创建接口仅对 librarian 开放。"""
    await _seed_tenant(db_session)
    token = await _register_user(client, student_no="2024002")  # student role
    response = await client.post(
        "/api/v1/books",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Test Book", "author": "Author", "total_copies": 2},
    )
    assert response.status_code == 403


async def test_create_then_list_book(client, db_session):
    """测试 librarian 创建图书后能列出:覆盖提权 → 重登 → 创建 → 列表完整流程,新书应出现在 items 中。"""
    await _seed_tenant(db_session)
    token = await _register_user(client, student_no="2024003")
    # Need to upgrade to librarian role — directly via DB
    from app.models import User
    from sqlalchemy import select, update
    await db_session.execute(
        update(User).where(User.student_no == "2024003").values(role="librarian")
    )
    await db_session.commit()
    # Re-login to get fresh token with new role
    login = await client.post(
        "/api/v1/auth/login",
        json={"student_no": "2024003", "password": "test_pass_123"},
    )
    token = login.json()["access_token"]

    create = await client.post(
        "/api/v1/books",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "深入理解计算机系统", "author": "Bryant", "total_copies": 5},
    )
    assert create.status_code == 201, create.text
    book_id = create.json()["id"]

    listing = await client.get(
        "/api/v1/books",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == book_id