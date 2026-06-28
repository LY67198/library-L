from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    """Health check - verifies DB connectivity."""
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
