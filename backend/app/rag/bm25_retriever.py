"""BM25 检索器 — 封装 WhooshIndexManager 并产出 Hit 对象。"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.rag.bm25_index import WhooshIndexManager


@dataclass(frozen=True)
class Hit:
    """单条召回命中 — 在检索阶段使用的统一结构。"""

    chunk_id: str
    source_id: str
    title: str
    content: str
    score: float
    rank: int  # 1-based rank within this retriever


class BM25Retriever:
    """BM25 关键词检索器 — 基于 Whoosh 实现。"""

    def __init__(self, index_manager: WhooshIndexManager):
        """初始化 BM25Retriever。

        参数:
            index_manager: 已构造的 WhooshIndexManager 实例。
        """
        self.index_manager = index_manager

    async def retrieve(self, query: str, tenant_id: UUID, top_k: int = 20) -> list[Hit]:
        """对 query 执行 BM25 检索。

        参数:
            query: 查询字符串。
            tenant_id: 租户 UUID(用于隔离索引)。
            top_k: 返回的最大命中数,默认 20。

        返回值:
            list[Hit]: 按相关度排序的命中列表,`rank` 从 1 起。
        """
        raw = self.index_manager.search(tenant_id, query, top_k=top_k)
        return [
            Hit(
                chunk_id=r["chunk_id"],
                source_id=r["source_id"],
                title=r["title"],
                content=r["content"],
                score=r["score"],
                rank=i + 1,
            )
            for i, r in enumerate(raw)
        ]