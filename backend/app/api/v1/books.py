"""馆藏图书路由 — 提供图书的列表、详情、创建、更新与删除接口(写操作限图书管理员)。"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import Forbidden
from app.models import User
from app.schemas.book import BookCreate, BookResponse, BookUpdate
from app.schemas.pagination import Page, PageRequest
from app.services.book_service import BookService

router = APIRouter(prefix="/books", tags=["books"])


def _require_librarian(user: User) -> None:
    """校验当前用户具备图书管理员权限(librarian / admin)。

    参数:
        user: 当前请求对应的已登录用户。

    返回值:
        None: 仅做权限校验,无返回。

    抛出:
        Forbidden: 当用户角色不在允许列表时抛出。
    """
    if user.role not in ("librarian", "admin"):
        raise Forbidden("Librarian role required")


@router.get("", response_model=Page[BookResponse])
async def list_books(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = None,
    q: str | None = None,
) -> Page[BookResponse]:
    """分页查询图书列表 — 支持按分类过滤与关键词模糊搜索。

    参数:
        request: FastAPI 请求对象,用于读取当前租户上下文。
        db: 异步数据库会话。
        _: 当前登录用户(此处仅用于鉴权占位)。
        page: 页码,从 1 开始。
        page_size: 每页大小,1~100。
        category: 可选的图书分类过滤条件。
        q: 可选的关键词搜索。

    返回值:
        Page[BookResponse]: 分页后的图书响应列表,包含 items / page / page_size / total。
    """
    tenant_id: UUID = request.state.tenant_id
    service = BookService(db)
    items, total = await service.list(
        tenant_id, category=category, q=q, page=page, page_size=page_size
    )
    return Page[BookResponse](
        items=[BookResponse.model_validate(b) for b in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(
    request: Request,
    book_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> BookResponse:
    """按 ID 查询图书详情。

    参数:
        request: FastAPI 请求对象,用于读取当前租户上下文。
        book_id: 图书主键 ID(路径参数)。
        db: 异步数据库会话。
        _: 当前登录用户(此处仅用于鉴权占位)。

    返回值:
        BookResponse: 匹配到的图书详情。
    """
    tenant_id: UUID = request.state.tenant_id
    service = BookService(db)
    book = await service.get(book_id, tenant_id)
    return BookResponse.model_validate(book)


@router.post("", response_model=BookResponse, status_code=201)
async def create_book(
    request: Request,
    payload: BookCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> BookResponse:
    """创建图书 — 仅限图书管理员(librarian / admin)操作。

    参数:
        request: FastAPI 请求对象,用于读取当前租户上下文。
        payload: 图书创建请求体。
        db: 异步数据库会话。
        user: 当前登录用户,用于权限校验。

    返回值:
        BookResponse: 新建后的图书详情。
    """
    _require_librarian(user)
    tenant_id: UUID = request.state.tenant_id
    service = BookService(db)
    book = await service.create(
        tenant_id=tenant_id,
        data=payload.model_dump(),
    )
    return BookResponse.model_validate(book)


@router.patch("/{book_id}", response_model=BookResponse)
async def update_book(
    request: Request,
    book_id: int,
    payload: BookUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> BookResponse:
    """局部更新图书信息 — 仅限图书管理员操作,只更新提供的字段。

    参数:
        request: FastAPI 请求对象,用于读取当前租户上下文。
        book_id: 图书主键 ID(路径参数)。
        payload: 图书更新请求体,字段可选。
        db: 异步数据库会话。
        user: 当前登录用户,用于权限校验。

    返回值:
        BookResponse: 更新后的图书详情。
    """
    _require_librarian(user)
    tenant_id: UUID = request.state.tenant_id
    service = BookService(db)
    book = await service.update(book_id, tenant_id, payload.model_dump(exclude_unset=True))
    return BookResponse.model_validate(book)


@router.delete("/{book_id}", status_code=204)
async def delete_book(
    request: Request,
    book_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    """删除图书 — 仅限图书管理员操作,无返回内容(204)。

    参数:
        request: FastAPI 请求对象,用于读取当前租户上下文。
        book_id: 图书主键 ID(路径参数)。
        db: 异步数据库会话。
        user: 当前登录用户,用于权限校验。

    返回值:
        None: 成功删除后无返回体。
    """
    _require_librarian(user)
    tenant_id: UUID = request.state.tenant_id
    service = BookService(db)
    await service.delete(book_id, tenant_id)
