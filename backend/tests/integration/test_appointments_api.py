from datetime import datetime, timedelta, timezone
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


async def _register_student(client, student_no):
    r = await client.post(
        "/api/v1/auth/register",
        json={"student_no": student_no, "password": "test_pass_123", "full_name": student_no},
    )
    return r.json()["access_token"]


async def _create_seat(db_session, code="A-101"):
    from app.models import Seat
    seat = Seat(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        code=code,
        floor="1F",
        zone="silent",
        status="available",
        has_power=True,
        has_monitor=False,
        coord_x=10,
        coord_y=20,
    )
    db_session.add(seat)
    await db_session.commit()
    await db_session.refresh(seat)
    return seat


async def test_book_seat_happy_path(client, db_session):
    await _seed_tenant(db_session)
    seat = await _create_seat(db_session, code="A-101")
    token = await _register_student(client, "2024100")
    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=1)
    end = start + timedelta(hours=2)

    response = await client.post(
        "/api/v1/appointments",
        headers={"Authorization": f"Bearer {token}"},
        json={"seat_id": seat.id, "start_time": start.isoformat(), "end_time": end.isoformat()},
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "confirmed"


async def test_book_seat_conflict_returns_409(client, db_session):
    await _seed_tenant(db_session)
    seat = await _create_seat(db_session, code="A-102")
    token1 = await _register_student(client, "2024101")
    token2 = await _register_student(client, "2024102")
    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=2)
    end = start + timedelta(hours=2)

    r1 = await client.post(
        "/api/v1/appointments",
        headers={"Authorization": f"Bearer {token1}"},
        json={"seat_id": seat.id, "start_time": start.isoformat(), "end_time": end.isoformat()},
    )
    assert r1.status_code == 201

    r2 = await client.post(
        "/api/v1/appointments",
        headers={"Authorization": f"Bearer {token2}"},
        json={"seat_id": seat.id, "start_time": start.isoformat(), "end_time": end.isoformat()},
    )
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "conflict"