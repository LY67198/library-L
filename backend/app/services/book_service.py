from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, NotFound
from app.models import Book
from app.repositories.book_repository import BookRepository


class BookService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = BookRepository(session)

    async def list(
        self,
        tenant_id: UUID,
        *,
        category: str | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Book], int]:
        return await self.repo.list(
            tenant_id, category=category, q=q, page=page, page_size=page_size
        )

    async def get(self, book_id: int, tenant_id: UUID) -> Book:
        book = await self.repo.get_by_id(book_id, tenant_id)
        if book is None:
            raise NotFound(f"Book {book_id} not found")
        return book

    async def create(self, *, tenant_id: UUID, data: dict) -> Book:
        if data.get("available_copies", 1) > data.get("total_copies", 1):
            raise Conflict("available_copies cannot exceed total_copies")
        return await self.repo.create(tenant_id=tenant_id, data=data)

    async def update(self, book_id: int, tenant_id: UUID, data: dict) -> Book:
        book = await self.get(book_id, tenant_id)
        new_total = data.get("total_copies", book.total_copies)
        new_avail = data.get("available_copies", book.available_copies)
        if new_avail > new_total:
            raise Conflict("available_copies cannot exceed total_copies")
        return await self.repo.update(book, data)

    async def delete(self, book_id: int, tenant_id: UUID) -> None:
        book = await self.get(book_id, tenant_id)
        await self.repo.delete(book)