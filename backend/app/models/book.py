"""图书模型 — 租户内的馆藏图书记录,带 ISBN、馆藏副本数与灵活扩展字段。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedMixin
from app.models.enums import BookStatus


class Book(TenantScopedMixin):
    """图书实体:隶属于某个租户,记录书名/作者/分类/馆藏位置/副本数等。

    说明:
        ``metadata`` 是 SQLAlchemy 声明式 API 在 ORM 类上的保留属性名
        (指向 ``MetaData`` 实例)。因此数据库列 ``metadata`` 在 Python 侧
        映射为 :attr:`book_metadata`,并通过 ``__init__`` / ``__getattribute__``
        / ``__setattr__`` 在实例层级把公开名 ``metadata`` 透明地路由到
        底层 ``book_metadata``。Pydantic schema 与 service/repo 层使用
        公开名 ``metadata``,无需感知这一重映射。
    """

    __tablename__ = "books"
    __table_args__ = (
        Index("idx_books_tenant_title", "tenant_id", "title"),
        Index("idx_books_tenant_author", "tenant_id", "author"),
        Index("idx_books_tenant_category", "tenant_id", "category"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    isbn: Mapped[str | None] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    author: Mapped[str | None] = mapped_column(String(256))
    publisher: Mapped[str | None] = mapped_column(String(128))
    category: Mapped[str | None] = mapped_column(String(32))
    location: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=BookStatus.available.value)
    total_copies: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    available_copies: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # SQLAlchemy 的声明式 API 在 ORM 类上保留了属性名 ``metadata``(指向
    # 表的 ``MetaData``)。因此 SQL 列 ``"metadata"`` 在 Python 端映射为
    # ``book_metadata``,并仅在实例层级通过 ``__getattr__`` / ``__setattr__``
    # 把它以 ``metadata`` 形式对外暴露。Pydantic schema(``BookCreate``、
    # ``BookResponse``)以及 service / repo 层都使用公开名 ``metadata``,
    # 这一重映射对调用方完全透明。
    book_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __init__(self, **kwargs: Any) -> None:
        """初始化 ``Book`` 实例,把公开的关键字参数 ``metadata`` 映射到底层 ``book_metadata``。

        参数:
            **kwargs: 构造参数,支持 ``metadata=...``(Pydantic schema 与
                公开 API 使用)与 ``book_metadata=...``(映射字段)两种写法。

        返回值:
            None
        """
        # 将 Pydantic schema 与公开 API 使用的关键字参数 ``metadata``
        # 翻译为映射字段 ``book_metadata``,使 ``Book(metadata=...)`` 不报错。
        if "metadata" in kwargs and "book_metadata" not in kwargs:
            kwargs["book_metadata"] = kwargs.pop("metadata")
        super().__init__(**kwargs)

    def __getattribute__(self, name: str) -> Any:
        """获取实例属性;把实例层的 ``metadata`` 访问路由到底层 ``book_metadata``。

        参数:
            name: 要获取的属性名。

        返回值:
            Any: 对应属性的值。

        说明:
            之所以使用 ``__getattribute__`` 而不是 ``__getattr__``,是因为
            SQLAlchemy 声明式基类会在类上安装 ``metadata`` 属性(指向
            ``MetaData`` 实例),会遮蔽实例层 ``__getattr__`` 的回退逻辑。
        """
        # 将实例层的 ``metadata`` 访问路由到映射字段 ``book_metadata``。
        if name == "metadata":
            try:
                return super().__getattribute__("book_metadata")
            except AttributeError:
                raise AttributeError(name)
        return super().__getattribute__(name)

    def __setattr__(self, name: str, value: Any) -> None:
        """设置实例属性;把 ``book.metadata = ...`` 翻译为对 ``book_metadata`` 的写入。

        参数:
            name: 要设置的属性名。
            value: 要写入的值。

        返回值:
            None
        """
        # 将 ``book.metadata = ...`` 翻译为对映射字段 ``book_metadata`` 的
        # 写入,以保证更新走 SQLAlchemy 的 instrumented attribute 通道。
        if name == "metadata":
            super().__setattr__("book_metadata", value)
            return
        super().__setattr__(name, value)
