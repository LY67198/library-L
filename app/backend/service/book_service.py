"""图书管理业务逻辑"""

from __future__ import annotations

import csv
import io
import logging

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.schemas.book import BookCreate, BookUpdate
from models import Book

logger = logging.getLogger(__name__)


class BookService:

    def __init__(self, db: AsyncSession):
        self._db = db

    async def list_books(
        self, q: str = "", category: str = "", offset: int = 0, limit: int = 20
    ) -> tuple[list[Book], int]:
        """分页查询图书，支持搜索和分类筛选"""
        stmt = select(Book)
        count_stmt = select(func.count(Book.id))

        if q:
            pattern = f"%{q}%"
            filter_clause = or_(
                Book.title.ilike(pattern),
                Book.author.ilike(pattern),
                Book.isbn.ilike(pattern),
            )
            stmt = stmt.where(filter_clause)
            count_stmt = count_stmt.where(filter_clause)

        if category:
            stmt = stmt.where(Book.category == category)
            count_stmt = count_stmt.where(Book.category == category)

        total_result = await self._db.execute(count_stmt)
        total = total_result.scalar() or 0

        result = await self._db.execute(
            stmt.order_by(Book.created_at.desc()).offset(offset).limit(limit)
        )
        books = list(result.scalars().all())
        return books, total

    async def get_book(self, book_id: str) -> Book | None:
        """获取单条图书"""
        result = await self._db.execute(select(Book).where(Book.id == book_id))
        return result.scalar_one_or_none()

    async def create_book(self, data: BookCreate) -> Book:
        """新增图书"""
        if data.available > data.total:
            raise ValueError("可借数不能大于总册数")
        book = Book(**data.model_dump())
        self._db.add(book)
        await self._db.commit()
        await self._db.refresh(book)
        return book

    async def update_book(self, book_id: str, data: BookUpdate) -> Book:
        """更新图书"""
        book = await self.get_book(book_id)
        if book is None:
            raise ValueError("图书不存在")
        update_data = data.model_dump(exclude_unset=True)
        if "available" in update_data and "total" not in update_data:
            if update_data["available"] > book.total:
                raise ValueError("可借数不能大于总册数")
        if "total" in update_data and "available" not in update_data:
            if book.available > update_data["total"]:
                raise ValueError("可借数不能大于总册数")
        if "total" in update_data and "available" in update_data:
            if update_data["available"] > update_data["total"]:
                raise ValueError("可借数不能大于总册数")
        for key, value in update_data.items():
            setattr(book, key, value)
        await self._db.commit()
        await self._db.refresh(book)
        return book

    async def delete_book(self, book_id: str) -> bool:
        """删除图书，返回是否成功"""
        book = await self.get_book(book_id)
        if book is None:
            return False
        await self._db.delete(book)
        await self._db.commit()
        return True

    async def import_json(self, items: list[BookCreate]) -> dict:
        """批量导入 JSON 数据"""
        success = 0
        errors = 0
        for item in items:
            try:
                await self.create_book(item)
                success += 1
            except Exception as exc:
                logger.warning(f"导入失败 {item.title}: {exc}")
                errors += 1
        return {"success": success, "errors": errors}

    async def import_csv(self, file_content: bytes) -> dict:
        """批量导入 CSV 文件"""
        success = 0
        errors = 0
        reader = csv.DictReader(io.StringIO(file_content.decode("utf-8-sig")))
        for row in reader:
            try:
                data = BookCreate(
                    title=row.get("title", ""),
                    author=row.get("author", ""),
                    isbn=row.get("isbn") or None,
                    publisher=row.get("publisher") or None,
                    publish_year=int(row["publish_year"]) if row.get("publish_year") else None,
                    category=row.get("category") or None,
                    location=row.get("location") or None,
                    total=int(row.get("total", 1)),
                    available=int(row.get("available", 1)),
                )
                await self.create_book(data)
                success += 1
            except Exception as exc:
                logger.warning(f"CSV 导入失败行 {reader.line_num}: {exc}")
                errors += 1
        return {"success": success, "errors": errors}
