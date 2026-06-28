import pytest

pytestmark = pytest.mark.integration


async def test_health_returns_ok(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["components"]["database"]["ok"] is True


async def test_health_no_auth_required(client):
    """Health endpoint must work without Authorization header."""
    response = await client.get("/api/v1/health")  # no headers
    assert response.status_code == 200
