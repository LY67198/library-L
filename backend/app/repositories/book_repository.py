from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Book


class BookRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, book_id: int, tenant_id: UUID) -> Book | None:
        stmt = select(Book).where(Book.id == book_id, Book.tenant_id == tenant_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        tenant_id: UUID,
        *,
        category: str | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Book], int]:
        stmt = select(Book).where(Book.tenant_id == tenant_id)
        count_stmt = select(func.count()).select_from(Book).where(Book.tenant_id == tenant_id)
        if category:
            stmt = stmt.where(Book.category == category)
            count_stmt = count_stmt.where(Book.category == category)
        if q:
            like = f"%{q}%"
            stmt = stmt.where((Book.title.ilike(like)) | (Book.author.ilike(like)))
            count_stmt = count_stmt.where((Book.title.ilike(like)) | (Book.author.ilike(like)))
        stmt = stmt.order_by(Book.id).offset((page - 1) * page_size).limit(page_size)
        items = (await self.session.execute(stmt)).scalars().all()
        total = (await self.session.execute(count_stmt)).scalar_one()
        return list(items), int(total)

    async def create(self, *, tenant_id: UUID, data: dict) -> Book:
        book = Book(tenant_id=tenant_id, **data)
        self.session.add(book)
        await self.session.flush()
        await self.session.refresh(book)
        return book

    async def update(self, book: Book, data: dict) -> Book:
        for k, v in data.items():
            if v is not None:
                setattr(book, k, v)
        await self.session.flush()
        await self.session.refresh(book)
        return book

    async def delete(self, book: Book) -> None:
        await self.session.delete(book)
        await self.session.flush()