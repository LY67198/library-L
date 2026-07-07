"""馆藏检索接口 — 真实数据库查询"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.schemas.book import BookListResponse, BookResponse
from backend.service.book_service import BookService
from core.database import get_db

router = APIRouter(prefix="/api/v1/books", tags=["books"])


@router.get("", response_model=BookListResponse)
async def search_books(
    q: str = Query(default="", min_length=0),
    category: str = Query(default=""),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """图书搜索 — 支持书名/作者/ISBN 模糊搜索 + 分类筛选"""
    service = BookService(db)
    books, total = await service.list_books(q=q, category=category, offset=offset, limit=limit)
    return BookListResponse(
        items=[BookResponse.model_validate(b).model_dump() for b in books],
        total=total,
        offset=offset,
        limit=limit,
    )
