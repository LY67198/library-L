"""健康检查路由 — 提供数据库连通性探测,供负载均衡 / 探针使用。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    """健康检查端点 — 通过执行 SELECT 1 验证数据库可达性。

    参数:
        db: 异步数据库会话依赖,用于执行连通性探测 SQL。

    返回值:
        dict: 包含整体 status("ok"/"degraded")与各组件(database)健康详情的字典。
    """
    db_ok = True
    db_error: str | None = None
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_ok = False
        db_error = str(e)

    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "components": {
            "database": {"ok": db_ok, "error": db_error},
        },
    }
