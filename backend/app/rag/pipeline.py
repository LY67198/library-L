"""混合检索器 — BM25 + Dense 并发召回 → RRF 融合 → Rerank 重排 → top-K。"""
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
    """混合检索结果 — 包含原始 query 与 rerank 后的命中列表。"""

    query: str
    hits: list[Hit]  # post-rerank, top_k


class HybridRetriever:
    """混合检索器 — 串联 BM25 / Dense / RRF / Rerank 三阶段流水线。"""

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
        """初始化 HybridRetriever。

        参数:
            bm25: BM25 检索器。
            dense: Dense 向量检索器。
            rerank: Rerank 客户端。
            bm25_top_k: BM25 召回数量,默认 20。
            dense_top_k: Dense 召回数量,默认 20。
            rrf_top_k: RRF 融合后保留的最大候选数,默认 30。
            rerank_top_k: Rerank 重排后返回的 top-K,默认 5。
        """
        self.bm25 = bm25
        self.dense = dense
        self.rerank = rerank
        self.bm25_top_k = bm25_top_k
        self.dense_top_k = dense_top_k
        self.rrf_top_k = rrf_top_k
        self.rerank_top_k = rerank_top_k

    async def retrieve(self, query: str, tenant_id: UUID) -> RetrievalResult:
        """执行三阶段混合检索流水线。

        阶段:
            1. 并发召回:BM25 与 Dense 通过 `asyncio.gather` 并发执行,
               任一路异常被吞掉转为空列表(failure-tolerant)。
            2. RRF 融合:对两路召回按 `1 / (k + rank)` 累加得分,排序后
               取前 `rrf_top_k` 作为重排候选。
            3. Rerank 重排:使用 Rerank 客户端对融合候选重打分,返回
               前 `rerank_top_k` 个,新分数写入 `score`,重新计算 `rank`。

        参数:
            query: 查询字符串。
            tenant_id: 租户 UUID。

        返回值:
            RetrievalResult: 包含原始 query 与重排后的命中列表。
        """
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