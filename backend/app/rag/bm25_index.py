"""Whoosh 索引管理器 — 每个租户一个索引,持久化到磁盘。"""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

from whoosh import index
from whoosh.analysis import StemmingAnalyzer
from whoosh.fields import ID, TEXT, Schema
from whoosh.qparser import MultifieldParser

_SCHEMA = Schema(
    chunk_id=ID(stored=True, unique=True),
    tenant_id=ID(stored=True),
    source_id=ID(stored=True),
    title=TEXT(stored=True),
    content=TEXT(stored=True, analyzer=StemmingAnalyzer()),
)


class WhooshIndexManager:
    """Whoosh 索引管理器 — 在基础目录下按租户分子目录管理多个索引。"""

    def __init__(self, base_dir: Path | str):
        """初始化 WhooshIndexManager,确保基础目录存在。

        参数:
            base_dir: 索引持久化的根目录。
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _tenant_dir(self, tenant_id: UUID) -> Path:
        """获取/创建指定租户的索引子目录。

        参数:
            tenant_id: 租户 UUID。

        返回值:
            Path: 该租户对应的索引目录路径。
        """
        d = self.base_dir / str(tenant_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_index(self, tenant_id: UUID):
        """打开或创建指定租户的索引。

        参数:
            tenant_id: 租户 UUID。

        返回值:
            whoosh.index.FileIndex: 对应租户的 Whoosh 索引实例。
        """
        d = self._tenant_dir(tenant_id)
        ix = index.open_dir(str(d)) if index.exists_in(str(d)) else index.create_in(str(d), _SCHEMA)
        return ix

    def add_chunks(
        self,
        tenant_id: UUID,
        chunks: list[tuple[str, str, str, str]],  # (chunk_id, source_id, title, content)
    ) -> None:
        """批量写入 chunks,以 `chunk_id` 作为去重键。

        参数:
            tenant_id: 租户 UUID。
            chunks: `(chunk_id, source_id, title, content)` 元组列表。

        返回值:
            None: 无返回值。
        """
        ix = self.get_index(tenant_id)
        writer = ix.writer()
        for chunk_id, source_id, title, content in chunks:
            writer.update_document(
                chunk_id=chunk_id,
                tenant_id=str(tenant_id),
                source_id=source_id,
                title=title,
                content=content,
            )
        writer.commit()

    def delete_by_source(self, tenant_id: UUID, source_id: str) -> None:
        """删除指定 source 的全部 chunks。

        参数:
            tenant_id: 租户 UUID。
            source_id: 文档/数据源 ID。

        返回值:
            None: 无返回值。
        """
        ix = self.get_index(tenant_id)
        writer = ix.writer()
        writer.delete_by_term("source_id", source_id)
        writer.commit()

    def search(self, tenant_id: UUID, query: str, top_k: int = 20) -> list[dict]:
        """在租户索引中检索 query。

        参数:
            tenant_id: 租户 UUID。
            query: 查询字符串。
            top_k: 返回的最大命中数,默认 20。

        返回值:
            list[dict]: 命中列表,元素字段包含 `chunk_id`、`source_id`、`title`、`content`、`score`。
        """
        ix = self.get_index(tenant_id)
        parser = MultifieldParser(["title", "content"], schema=ix.schema)
        parsed = parser.parse(query)
        results: list[dict] = []
        with ix.searcher() as searcher:
            hits = searcher.search(parsed, limit=top_k)
            for hit in hits:
                results.append(
                    {
                        "chunk_id": hit["chunk_id"],
                        "source_id": hit["source_id"],
                        "title": hit.get("title", ""),
                        "content": hit["content"],
                        "score": float(hit.score),
                    }
                )
        return results