from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Book


class BookRepository:
    """馆藏图书表的数据访问对象,提供分页、按分类过滤与关键字模糊检索能力。"""

    def __init__(self, session: AsyncSession):
        """初始化仓储实例。

        参数:
            session: SQLAlchemy 异步会话
        """
        self.session = session

    async def get_by_id(self, book_id: int, tenant_id: UUID) -> Book | None:
        """按主键与租户 ID 查询单本图书。

        参数:
            book_id: 图书主键 ID
            tenant_id: 所属租户 ID

        返回值:
            Book | None: 命中则返回图书对象,否则返回 None
        """
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
        """分页查询图书列表,支持按分类与标题/作者模糊过滤。

        参数:
            tenant_id: 所属租户 ID
            category: 分类过滤条件(可选)
            q: 关键字,匹配书名或作者(可选)
            page: 页码,从 1 开始
            page_size: 每页条目数

        返回值:
            tuple[list[Book], int]: 当前页图书列表与符合过滤条件的总数
        """
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
        """创建一条图书记录。

        参数:
            tenant_id: 所属租户 ID
            data: 图书字段字典(由调用方校验完整性)

        返回值:
            Book: 已写入数据库的图书对象
        """
        book = Book(tenant_id=tenant_id, **data)
        self.session.add(book)
        await self.session.flush()
        await self.session.refresh(book)
        return book

    async def update(self, book: Book, data: dict) -> Book:
        """更新指定图书的字段(只覆盖非空值)。

        参数:
            book: 已加载的图书 ORM 实例
            data: 待更新字段字典,值为 None 的键将被忽略

        返回值:
            Book: 更新后的图书对象
        """
        for k, v in data.items():
            if v is not None:
                setattr(book, k, v)
        await self.session.flush()
        await self.session.refresh(book)
        return book

    async def delete(self, book: Book) -> None:
        """删除指定图书。

        参数:
            book: 已加载的图书 ORM 实例
        """
        await self.session.delete(book)
        await self.session.flush()