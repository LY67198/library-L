"""文档管理接口 — 需 admin 权限"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.schemas.document import DocListResponse, DocResponse
from backend.service.doc_service import DocService
from core.database import get_db
from core.deps import require_admin
from models import User

router = APIRouter()


@router.get("/api/v1/admin/documents", response_model=DocListResponse)
async def admin_list_docs(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """文档列表"""
    service = DocService(db)
    docs, total = await service.list_docs()
    return DocListResponse(
        items=[DocResponse.model_validate(d).model_dump() for d in docs],
        total=total,
    )


@router.post("/api/v1/admin/documents", status_code=status.HTTP_201_CREATED)
async def admin_upload_doc(
    title: str = Form(min_length=1, max_length=256),
    source_type: str = Form(default="policy", pattern="^(policy|rule|faq|other)$"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """上传 Markdown 文档 → 分块 → 嵌入 → ChromaDB"""
    content_bytes = await file.read()
    content = content_bytes.decode("utf-8")
    filename = file.filename or "unknown.md"

    service = DocService(db)
    try:
        doc = await service.upload(
            title=title,
            filename=filename,
            source_type=source_type,
            content=content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": str(exc)})
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail={"error": "processing_error", "message": str(exc)})

    return DocResponse.model_validate(doc).model_dump()


@router.delete("/api/v1/admin/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_doc(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """删除文档 + ChromaDB chunks"""
    service = DocService(db)
    ok = await service.delete(doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "文档不存在"})
