"""SQL 图书字段精确查询 — PostgreSQL LIKE 匹配"""

from __future__ import annotations

from typing import Any


class SQLBookLookup:
    """基于 PostgreSQL 的图书字段检索器"""

    def __init__(self, db_url: str = ""):
        self._db_url = db_url
        self._engine: Any = None

    def _ensure_initialized(self):
        if self._engine is not None:
            return
        if not self._db_url:
            raise RuntimeError("数据库 URL 未配置")
        try:
            from sqlalchemy import create_engine, text

            self._engine = create_engine(self._db_url)
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except ImportError:
            raise RuntimeError("sqlalchemy 未安装，请执行: uv add sqlalchemy")
        except Exception as exc:
            raise RuntimeError(f"数据库连接失败: {exc}")

    def search(self, query: str, top_k: int = 10, **kwargs) -> list[dict]:
        """按书名、作者、ISBN 进行 LIKE 模糊检索"""
        if not self._db_url:
            return self._stub_results(query, top_k)
        try:
            self._ensure_initialized()
            from sqlalchemy import text

            pattern = f"%{query}%"
            with self._engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT id, title, author, isbn, location, available "
                        "FROM books "
                        "WHERE title LIKE :p OR author LIKE :p OR isbn LIKE :p "
                        "LIMIT :limit"
                    ),
                    {"p": pattern, "limit": top_k},
                )
                rows = result.fetchall()
                return [
                    {
                        "content": f"《{row[1]}》 — {row[2]}",
                        "metadata": {
                            "id": str(row[0]),
                            "title": row[1],
                            "author": row[2],
                            "isbn": row[3],
                            "location": row[4],
                            "available": row[5],
                            "source": "books_db",
                        },
                        "score": 0.95,
                    }
                    for row in rows
                ]
        except RuntimeError:
            raise
        except Exception:
            return self._stub_results(query, top_k)

    def _stub_results(self, query: str, top_k: int) -> list[dict]:
        """数据库不可用时的占位结果"""
        return [
            {
                "content": f"Placeholder book result for: {query}",
                "metadata": {"source": "stub", "title": query},
                "score": 0.5,
            }
            for _ in range(min(top_k, 3))
        ]
