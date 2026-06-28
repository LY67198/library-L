"""Dense 向量检索器 — 将 query 向量化后查询 ChromaDB,产出 Hit 列表。"""
from __future__ import annotations

from uuid import UUID

from app.clients.embedding_client import EmbeddingClient
from app.rag.bm25_retriever import Hit
from app.rag.chroma_store import ChromaStore


class DenseRetriever:
    """Dense 向量检索器 — 组合 EmbeddingClient 与 ChromaStore 实现语义召回。"""

    def __init__(self, chroma: ChromaStore, embedding: EmbeddingClient):
        """初始化 DenseRetriever。

        参数:
            chroma: ChromaDB 存储实例。
            embedding: Embedding 客户端实例。
        """
        self.chroma = chroma
        self.embedding = embedding

    async def retrieve(self, query: str, tenant_id: UUID, top_k: int = 20) -> list[Hit]:
        """对 query 执行 dense 向量召回。

        参数:
            query: 查询字符串。
            tenant_id: 租户 UUID(用于隔离 collection)。
            top_k: 返回的最大命中数,默认 20。

        返回值:
            list[Hit]: 按相似度排序的命中列表,`rank` 从 1 起。
        """
        vectors = await self.embedding.embed([query])
        if not vectors:
            return []
        raw = self.chroma.query(tenant_id, query_embedding=vectors[0], top_k=top_k)
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
