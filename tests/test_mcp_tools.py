"""MCP Tool 函数逻辑测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from models import User


@pytest.fixture(autouse=True)
def _reset_mcp_user():
    """每个测试前重置用户 ContextVar"""
    from mcp_server import auth
    token = auth._current_mcp_user.set(None)
    yield
    auth._current_mcp_user.reset(token)


def _make_async_cm(mock_session):
    """创建模拟的 async context manager"""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


class TestSearchBooks:
    """search_books Tool"""

    @pytest.mark.asyncio
    async def test_returns_items_and_total(self):
        from models import Book

        mock_books = [
            Book(id="b1", title="Python入门", author="张三", isbn="123",
                 category="TP", location="3F", total=5, available=3),
            Book(id="b2", title="算法导论", author="李四", isbn="456",
                 category="TP", location="3F", total=2, available=1),
        ]
        mock_service = MagicMock()
        mock_service.list_books = AsyncMock(return_value=(mock_books, 2))

        mock_session = MagicMock()
        cm = _make_async_cm(mock_session)

        from mcp_server.tools import search_books_impl
        with patch("mcp_server.tools.BookService", return_value=mock_service), \
             patch("mcp_server.tools.get_session_factory", return_value=cm):
            result = await search_books_impl(query="Python", limit=5)
            assert result["items"][0]["title"] == "Python入门"
            assert result["total"] == 2

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty_list(self):
        mock_service = MagicMock()
        mock_service.list_books = AsyncMock(return_value=([], 0))

        mock_session = MagicMock()
        cm = _make_async_cm(mock_session)

        from mcp_server.tools import search_books_impl
        with patch("mcp_server.tools.BookService", return_value=mock_service), \
             patch("mcp_server.tools.get_session_factory", return_value=cm):
            result = await search_books_impl(query="")
            assert result["items"] == []
            assert result["total"] == 0


class TestListSeatsRequiresAuth:
    """list_seats 需要认证"""

    @pytest.mark.asyncio
    async def test_no_user_raises_error(self):
        from mcp_server.tools import list_seats_impl
        with pytest.raises(ValueError, match="未认证"):
            await list_seats_impl()


class TestBookSeat:
    """book_seat Tool"""

    @pytest.mark.asyncio
    async def test_returns_appointment_on_success(self):
        from mcp_server import auth

        user = User(
            id="u1", username="test", password_hash="x",
            display_name="Test", student_id="S001", api_key="key123"
        )
        auth._current_mcp_user.set(user)

        mock_service = MagicMock()
        expected = {
            "appointment_id": "apt-1", "seat_id": "seat-1",
            "floor_name": "1楼", "zone_name": "A区",
            "seat_number": "A01", "date": "2026-07-08", "slot": "morning"
        }
        mock_service.book_seat = AsyncMock(return_value=expected)

        mock_session = MagicMock()
        cm = _make_async_cm(mock_session)

        from mcp_server.tools import book_seat_impl
        with patch("mcp_server.tools.SeatService", return_value=mock_service), \
             patch("mcp_server.tools._get_lock", return_value=MagicMock()), \
             patch("mcp_server.tools.get_session_factory", return_value=cm):
            result = await book_seat_impl(seat_id="seat-1", date="2026-07-08", slot="morning")
            assert result["appointment_id"] == "apt-1"
            assert result["status"] == "booked"

    @pytest.mark.asyncio
    async def test_returns_error_on_conflict(self):
        from mcp_server import auth

        user = User(
            id="u1", username="test", password_hash="x",
            display_name="Test", student_id="S001", api_key="key123"
        )
        auth._current_mcp_user.set(user)

        mock_service = MagicMock()
        mock_service.book_seat = AsyncMock(side_effect=ValueError("座位已被预约"))

        mock_session = MagicMock()
        cm = _make_async_cm(mock_session)

        from mcp_server.tools import book_seat_impl
        with patch("mcp_server.tools.SeatService", return_value=mock_service), \
             patch("mcp_server.tools._get_lock", return_value=MagicMock()), \
             patch("mcp_server.tools.get_session_factory", return_value=cm):
            result = await book_seat_impl(seat_id="seat-1", date="2026-07-08", slot="morning")
            assert "error" in result


class TestCancelAppointment:
    """cancel_appointment Tool"""

    @pytest.mark.asyncio
    async def test_returns_success_on_cancel(self):
        from mcp_server import auth

        user = User(
            id="u1", username="test", password_hash="x",
            display_name="Test", student_id="S001", api_key="key123"
        )
        auth._current_mcp_user.set(user)

        mock_service = MagicMock()
        mock_service.cancel_appointment = AsyncMock(return_value={
            "appointment_id": "apt-1", "status": "cancelled"
        })

        mock_session = MagicMock()
        cm = _make_async_cm(mock_session)

        from mcp_server.tools import cancel_appointment_impl
        with patch("mcp_server.tools.SeatService", return_value=mock_service), \
             patch("mcp_server.tools._get_lock", return_value=MagicMock()), \
             patch("mcp_server.tools.get_session_factory", return_value=cm):
            result = await cancel_appointment_impl(appointment_id="apt-1")
            assert result["success"] is True
            assert result["cancelled_id"] == "apt-1"

    @pytest.mark.asyncio
    async def test_requires_auth(self):
        from mcp_server.tools import cancel_appointment_impl
        with pytest.raises(ValueError, match="未认证"):
            await cancel_appointment_impl(appointment_id="apt-1")
