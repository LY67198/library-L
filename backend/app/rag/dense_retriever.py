"""Dense retriever — embeds query, queries ChromaDB, returns Hit list."""
from __future__ import annotations

from uuid import UUID

from app.clients.embedding_client import EmbeddingClient
from app.rag.bm25_retriever import Hit
from app.rag.chroma_store import ChromaStore


class DenseRetriever:
    def __init__(self, chroma: ChromaStore, embedding: EmbeddingClient):
        self.chroma = chroma
        self.embedding = embedding

    async def retrieve(self, query: str, tenant_id: UUID, top_k: int = 20) -> list[Hit]:
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
