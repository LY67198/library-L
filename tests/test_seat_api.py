"""Seat API 集成测试 — 座位列表、预约、取消、冲突"""

import pytest
from httpx import ASGITransport, AsyncClient


async def _create_user_and_login(client, username="seatuser", password="password123",
                                  display_name="座位测试", student_id="2024001"):
    """辅助函数：注册 + 登录，返回 access_token"""
    await client.post("/api/v1/auth/register", json={
        "username": username,
        "password": password,
        "display_name": display_name,
        "student_id": student_id,
    })
    resp = await client.post("/api/v1/auth/login", json={
        "username": username, "password": password,
    })
    return resp.json()["access_token"]


async def _setup_overrides(db_session, redis_client):
    """注入测试数据库 + fakeredis 到 FastAPI app"""
    from core.database import get_db
    from core.lock import SeatLock
    from backend.router.seat_router import get_seat_lock

    from app_main import app

    async def override_get_db():
        yield db_session

    async def override_get_seat_lock():
        return SeatLock(redis_client)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_seat_lock] = override_get_seat_lock
    return app


@pytest.mark.asyncio
async def test_list_seats_empty(db_session, redis_client):
    """无座位数据时返回空列表"""
    app = await _setup_overrides(db_session, redis_client)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _create_user_and_login(client)
        resp = await client.get("/api/v1/seats", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["seats"] == []

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_book_seat_not_found(db_session, redis_client):
    """预约不存在的座位返回 422"""
    app = await _setup_overrides(db_session, redis_client)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _create_user_and_login(client)
        resp = await client.post(
            "/api/v1/seats/nonexistent-id/book",
            json={"date": "2026-07-10", "slot": "morning"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_seat_list_and_book_flow(db_session, redis_client):
    """完整预约流程：添加楼层→区域→座位→查列表→预约→查预约→取消"""
    app = await _setup_overrides(db_session, redis_client)

    from models import Floor, Zone, ZoneType, Seat

    floor = Floor(name="1楼", sort_order=1)
    zone = Zone(name="A区", zone_type=ZoneType.open, sort_order=1, floor=floor)
    seat1 = Seat(seat_number="001", zone=zone)
    seat2 = Seat(seat_number="002", zone=zone)
    db_session.add_all([floor, zone, seat1, seat2])
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _create_user_and_login(client)

        # List seats with date/slot — should all be available
        resp = await client.get(
            "/api/v1/seats?date=2026-07-10&slot=morning",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        seats = resp.json()["seats"]
        assert len(seats) == 2
        assert all(s["status"] == "available" for s in seats)

        # Book seat 1
        resp = await client.post(
            f"/api/v1/seats/{seat1.id}/book",
            json={"date": "2026-07-10", "slot": "morning"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["seat_id"] == seat1.id
        assert data["date"] == "2026-07-10"
        assert data["slot"] == "morning"

        # List again — seat1 should be booked
        resp = await client.get(
            "/api/v1/seats?date=2026-07-10&slot=morning",
            headers={"Authorization": f"Bearer {token}"},
        )
        seats = resp.json()["seats"]
        s1 = next(s for s in seats if s["seat_id"] == seat1.id)
        assert s1["status"] == "booked"
        assert s1["booked_by_me"] is True

        # Book same seat again — should get 409
        resp = await client.post(
            f"/api/v1/seats/{seat1.id}/book",
            json={"date": "2026-07-10", "slot": "morning"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (409, 422)

        # List my appointments
        resp = await client.get(
            "/api/v1/appointments",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        appts = resp.json()["appointments"]
        assert len(appts) == 1
        assert appts[0]["seat_id"] == seat1.id

        # Cancel appointment
        appt_id = appts[0]["appointment_id"]
        resp = await client.post(
            f"/api/v1/appointments/{appt_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

        # Seat should be available again
        resp = await client.get(
            "/api/v1/seats?date=2026-07-10&slot=morning",
            headers={"Authorization": f"Bearer {token}"},
        )
        s1 = next(s for s in resp.json()["seats"] if s["seat_id"] == seat1.id)
        assert s1["status"] == "available"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_unauthorized_access(db_session):
    """未登录访问需要认证的端点返回 401"""
    from core.database import get_db
    from app_main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/seats/any-id/book", json={
            "date": "2026-07-10", "slot": "morning",
        })
        assert resp.status_code == 401

    app.dependency_overrides.clear()
