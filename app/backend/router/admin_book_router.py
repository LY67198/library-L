"""图书管理接口 — 需 admin 权限"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.schemas.book import BookCreate, BookImportPayload, BookListResponse, BookResponse, BookUpdate
from backend.service.book_service import BookService
from core.database import get_db
from core.deps import require_admin
from models import User

router = APIRouter()


@router.get("/api/v1/admin/books", response_model=BookListResponse)
async def admin_list_books(
    q: str = Query(default=""),
    category: str = Query(default=""),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """图书分页列表（管理员）"""
    service = BookService(db)
    books, total = await service.list_books(q=q, category=category, offset=offset, limit=limit)
    return BookListResponse(
        items=[BookResponse.model_validate(b).model_dump() for b in books],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/api/v1/admin/books/{book_id}")
async def admin_get_book(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """图书详情（管理员）"""
    service = BookService(db)
    book = await service.get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "图书不存在"})
    return BookResponse.model_validate(book).model_dump()


@router.post("/api/v1/admin/books", status_code=status.HTTP_201_CREATED)
async def admin_create_book(
    body: BookCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """新增图书"""
    service = BookService(db)
    try:
        book = await service.create_book(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": str(exc)})
    return BookResponse.model_validate(book).model_dump()


@router.put("/api/v1/admin/books/{book_id}")
async def admin_update_book(
    book_id: str,
    body: BookUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """更新图书"""
    service = BookService(db)
    try:
        book = await service.update_book(book_id, body)
    except ValueError as exc:
        if str(exc) == "图书不存在":
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "图书不存在"})
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": str(exc)})
    return BookResponse.model_validate(book).model_dump()


@router.delete("/api/v1/admin/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_book(
    book_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """删除图书"""
    service = BookService(db)
    ok = await service.delete_book(book_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "图书不存在"})


@router.post("/api/v1/admin/books/import")
async def admin_import_books(
    request: Request,
    file: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """批量导入图书 — 支持 JSON 和 CSV"""
    service = BookService(db)

    content_type = request.headers.get("content-type", "")
    if file and "multipart/form-data" in content_type:
        content = await file.read()
        result = await service.import_csv(content)
    else:
        body = await request.json()
        payload = BookImportPayload(**body)
        result = await service.import_json(payload.items)

    return {"message": "导入完成", **result}
