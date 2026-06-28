"""图书领域服务 — 图书 CRUD 业务编排,含副本数一致性校验。"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, NotFound
from app.models import Book
from app.repositories.book_repository import BookRepository


class BookService:
    """馆藏图书领域服务,负责图书 CRUD 的业务校验与编排。"""

    def __init__(self, session: AsyncSession):
        """初始化服务实例。

        参数:
            session: SQLAlchemy 异步会话
        """
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
        """分页查询图书列表。

        参数:
            tenant_id: 所属租户 ID
            category: 分类过滤条件(可选)
            q: 关键字,匹配书名或作者(可选)
            page: 页码,从 1 开始
            page_size: 每页条目数

        返回值:
            tuple[list[Book], int]: 当前页图书列表与符合过滤条件的总数
        """
        return await self.repo.list(
            tenant_id, category=category, q=q, page=page, page_size=page_size
        )

    async def get(self, book_id: int, tenant_id: UUID) -> Book:
        """按主键查询图书。

        参数:
            book_id: 图书主键 ID
            tenant_id: 所属租户 ID

        返回值:
            Book: 图书对象

        抛出:
            NotFound: 图书不存在
        """
        book = await self.repo.get_by_id(book_id, tenant_id)
        if book is None:
            raise NotFound(f"Book {book_id} not found")
        return book

    async def create(self, *, tenant_id: UUID, data: dict) -> Book:
        """创建一条图书记录,校验可借册数不能超过总册数。

        参数:
            tenant_id: 所属租户 ID
            data: 图书字段字典

        返回值:
            Book: 新创建的图书对象

        抛出:
            Conflict: available_copies 大于 total_copies
        """
        if data.get("available_copies", 1) > data.get("total_copies", 1):
            raise Conflict("available_copies cannot exceed total_copies")
        return await self.repo.create(tenant_id=tenant_id, data=data)

    async def update(self, book_id: int, tenant_id: UUID, data: dict) -> Book:
        """更新图书字段,校验可借/总数关系。

        参数:
            book_id: 图书主键 ID
            tenant_id: 所属租户 ID
            data: 待更新字段字典

        返回值:
            Book: 更新后的图书对象

        抛出:
            NotFound: 图书不存在
            Conflict: 更新后 available_copies 大于 total_copies
        """
        book = await self.get(book_id, tenant_id)
        new_total = data.get("total_copies", book.total_copies)
        new_avail = data.get("available_copies", book.available_copies)
        if new_avail > new_total:
            raise Conflict("available_copies cannot exceed total_copies")
        return await self.repo.update(book, data)

    async def delete(self, book_id: int, tenant_id: UUID) -> None:
        """删除图书。

        参数:
            book_id: 图书主键 ID
            tenant_id: 所属租户 ID

        抛出:
            NotFound: 图书不存在
        """
        book = await self.get(book_id, tenant_id)
        await self.repo.delete(book)