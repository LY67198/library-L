"""BM25 retriever — wraps WhooshIndexManager and yields Hit objects."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.rag.bm25_index import WhooshIndexManager


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    source_id: str
    title: str
    content: str
    score: float
    rank: int  # 1-based rank within this retriever


class BM25Retriever:
    def __init__(self, index_manager: WhooshIndexManager):
        self.index_manager = index_manager

    async def retrieve(self, query: str, tenant_id: UUID, top_k: int = 20) -> list[Hit]:
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