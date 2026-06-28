from uuid import UUID

import pytest

pytestmark = pytest.mark.integration


async def _seed_tenant(db_session):
    from app.models import Tenant
    tid = UUID("00000000-0000-0000-0000-000000000001")
    if not await db_session.get(Tenant, tid):
        tenant = Tenant(id=tid, code="main_library", name="Main", status="active", config={})
        db_session.add(tenant)
        await db_session.commit()


async def _register_and_promote(client, db_session, student_no, role="librarian"):
    await client.post(
        "/api/v1/auth/register",
        json={"student_no": student_no, "password": "test_pass_123", "full_name": student_no},
    )
    from app.models import User
    from sqlalchemy import update
    await db_session.execute(
        update(User).where(User.student_no == student_no).values(role=role)
    )
    await db_session.commit()
    login = await client.post(
        "/api/v1/auth/login",
        json={"student_no": student_no, "password": "test_pass_123"},
    )
    return login.json()["access_token"]


async def test_create_policy_indexes_into_rag(client, db_session):
    await _seed_tenant(db_session)
    token = await _register_and_promote(client, db_session, "2024200", role="librarian")
    response = await client.post(
        "/api/v1/admin/policies",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "借阅规则",
            "content": "本科生最多借 10 本,期限 30 天。研究生最多借 20 本。",
            "category": "borrow",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["indexed_at"] is not None


async def test_create_policy_requires_librarian(client, db_session):
    await _seed_tenant(db_session)
    token = await _register_and_promote(client, db_session, "2024201", role="student")
    response = await client.post(
        "/api/v1/admin/policies",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "X", "content": "Y"},
    )
    assert response.status_code == 403