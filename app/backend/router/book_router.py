"""馆藏检索接口"""

from __future__ import annotations

from fastapi import APIRouter, Query

from backend.schemas.chat import BookSearchResult

router = APIRouter(prefix="/api/v1/books", tags=["books"])


@router.get("", response_model=list[BookSearchResult])
async def search_books(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
):
    """图书搜索 — 数据库未配置时返回占位结果"""
    return [
        BookSearchResult(
            id=f"STUB-{idx}",
            title=f"Placeholder: {q}",
            author="Unknown",
            location="待配置",
            available=0,
        )
        for idx in range(1, min(limit, 3) + 1)
    ]
