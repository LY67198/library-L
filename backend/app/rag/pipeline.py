"""HybridRetriever: BM25 + Dense (concurrent) → RRF → Rerank → top-K."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

from app.clients.rerank_client import RerankClient
from app.rag.bm25_retriever import BM25Retriever, Hit
from app.rag.dense_retriever import DenseRetriever
from app.rag.rrf import reciprocal_rank_fusion


@dataclass(frozen=True)
class RetrievalResult:
    query: str
    hits: list[Hit]  # post-rerank, top_k


class HybridRetriever:
    def __init__(
        self,
        bm25: BM25Retriever,
        dense: DenseRetriever,
        rerank: RerankClient,
        *,
        bm25_top_k: int = 20,
        dense_top_k: int = 20,
        rrf_top_k: int = 30,
        rerank_top_k: int = 5,
    ):
        self.bm25 = bm25
        self.dense = dense
        self.rerank = rerank
        self.bm25_top_k = bm25_top_k
        self.dense_top_k = dense_top_k
        self.rrf_top_k = rrf_top_k
        self.rerank_top_k = rerank_top_k

    async def retrieve(self, query: str, tenant_id: UUID) -> RetrievalResult:
        # Stage 1: BM25 + Dense in parallel (failure-tolerant)
        bm25_hits, dense_hits = await asyncio.gather(
            self.bm25.retrieve(query, tenant_id, top_k=self.bm25_top_k),
            self.dense.retrieve(query, tenant_id, top_k=self.dense_top_k),
            return_exceptions=True,
        )
        if isinstance(bm25_hits, Exception):
            bm25_hits = []
        if isinstance(dense_hits, Exception):
            dense_hits = []

        # Stage 2: RRF fusion
        fused = reciprocal_rank_fusion([bm25_hits, dense_hits])[: self.rrf_top_k]
        if not fused:
            return RetrievalResult(query=query, hits=[])

        # Stage 3: Rerank
        documents = [h.content for h in fused]
        reranked = await self.rerank.rerank(query, documents, top_n=self.rerank_top_k)
        # Map reranked indices back to fused hits, attach new score
        out: list[Hit] = []
        for orig_idx, new_score in reranked:
            base = fused[orig_idx]
            out.append(
                Hit(
                    chunk_id=base.chunk_id,
                    source_id=base.source_id,
                    title=base.title,
                    content=base.content,
                    score=new_score,
                    rank=len(out) + 1,
                )
            )
        return RetrievalResult(query=query, hits=out)