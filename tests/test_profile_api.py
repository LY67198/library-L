"""Profile API 集成测试"""

from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

from models import BorrowRecord, BorrowStatus


async def _create_user_and_login(client, username="profuser", password="password123",
                                display_name="画像测试", student_id="2024002"):
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


async def _setup_app(db_session):
    """注入测试数据库到 FastAPI app，同时覆盖 get_session_factory 避免 McpAuthMiddleware 创建真实 PG 连接"""
    import core.database as _db
    from core.database import get_db
    from app_main import app

    async def override_get_db():
        yield db_session

    @asynccontextmanager
    async def _test_session_factory():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # McpAuthMiddleware 直接调用 get_session_factory() 而非通过 FastAPI DI，
    # 必须替换以避免创建 PostgreSQL 引擎（测试环境使用 SQLite 内存库）。
    # 需要同时 patch core.database 和 mcp_server.auth 两个模块的引用，
    # 因为 mcp_server.auth 通过 from import 获得了局部引用。
    _original_core_factory = _db.get_session_factory
    _db.get_session_factory = lambda: _test_session_factory
    _db._session_factory = _test_session_factory  # 重置缓存

    import mcp_server.auth as _mcp_auth
    _original_mcp_factory = _mcp_auth.get_session_factory
    _mcp_auth.get_session_factory = lambda: _test_session_factory

    return app, (_original_core_factory, _original_mcp_factory)


async def _teardown_app(app, originals):
    """恢复 app 和 get_session_factory 到原始状态"""
    app.dependency_overrides.clear()
    import core.database as _db
    import mcp_server.auth as _mcp_auth
    _orig_core, _orig_mcp = originals
    _db.get_session_factory = _orig_core
    _db._session_factory = None
    _mcp_auth.get_session_factory = _orig_mcp


@pytest.mark.asyncio
async def test_get_profile_unauthenticated(db_session):
    """未登录访问 profile 返回 401"""
    app, orig_factory = await _setup_app(db_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/profile")
        assert resp.status_code == 401

    await _teardown_app(app, orig_factory)


@pytest.mark.asyncio
async def test_get_profile_all(db_session):
    """认证用户获取完整画像：user + appointments + borrow_records"""
    from models import Book

    app, orig_factory = await _setup_app(db_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _create_user_and_login(client)

        # 找到已登录用户的 ID
        from core.security import decode_token
        payload = decode_token(token)
        user_id = payload["sub"]

        # 创建一条借阅记录
        book = Book(title="测试图书", author="作者", isbn="978-0000000001")
        db_session.add(book)
        await db_session.flush()

        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        record = BorrowRecord(
            user_id=user_id,
            book_id=book.id,
            borrowed_at=now,
            due_at=now + timedelta(days=30),
            status=BorrowStatus.borrowed,
        )
        db_session.add(record)
        await db_session.commit()

        resp = await client.get(
            "/api/v1/profile?type=all",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"] is not None
        assert data["user"]["username"] == "profuser"
        assert data["user"]["display_name"] == "画像测试"
        assert data["user"]["student_id"] == "2024002"
        assert data["appointments"] == []
        assert isinstance(data["borrow_records"], list)
        assert len(data["borrow_records"]) == 1
        assert data["borrow_records"][0]["book_title"] == "测试图书"
        assert data["borrow_records"][0]["status"] == "borrowed"

    await _teardown_app(app, orig_factory)


@pytest.mark.asyncio
async def test_get_profile_personal_info(db_session):
    """type=personal_info 仅返回用户信息，appointments 和 borrow_records 为空数组"""
    app, orig_factory = await _setup_app(db_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _create_user_and_login(client)

        resp = await client.get(
            "/api/v1/profile?type=personal_info",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"] is not None
        assert data["user"]["username"] == "profuser"
        assert data["appointments"] == []
        assert data["borrow_records"] == []

    await _teardown_app(app, orig_factory)


@pytest.mark.asyncio
async def test_get_profile_borrowing_history(db_session):
    """type=borrowing_history 返回 user + borrow_records，appointments 为空"""
    from models import Book
    from core.security import decode_token

    app, orig_factory = await _setup_app(db_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _create_user_and_login(client)
        payload = decode_token(token)
        user_id = payload["sub"]

        book = Book(title="三体", author="刘慈欣", isbn="978-0000000002")
        db_session.add(book)
        await db_session.flush()

        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        record = BorrowRecord(
            user_id=user_id,
            book_id=book.id,
            borrowed_at=now,
            due_at=now + timedelta(days=60),
            status=BorrowStatus.borrowed,
        )
        db_session.add(record)
        await db_session.commit()

        resp = await client.get(
            "/api/v1/profile?type=borrowing_history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"] is not None
        assert data["appointments"] == []
        assert len(data["borrow_records"]) == 1
        assert data["borrow_records"][0]["book_title"] == "三体"

    await _teardown_app(app, orig_factory)
