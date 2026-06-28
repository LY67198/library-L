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
    _require_librarian(user)
    tenant_id: UUID = request.state.tenant_id
    service = BookService(db)
    await service.delete(book_id, tenant_id)