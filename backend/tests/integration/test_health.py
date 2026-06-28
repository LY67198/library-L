"""健康检查接口测试 — 验证 /api/v1/health 的 200 响应、组件状态与无需鉴权。"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_health_returns_ok(client):
    """测试健康检查接口:返回 200,status=ok,且 database 组件状态为 ok。"""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["components"]["database"]["ok"] is True


async def test_health_no_auth_required(client):
    """测试健康检查接口:无 Authorization 头也应返回 200,作为公开健康探针。"""
    response = await client.get("/api/v1/health")  # no headers
    assert response.status_code == 200
