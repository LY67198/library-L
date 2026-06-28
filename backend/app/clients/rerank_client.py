"""Qwen qwen3-rerank via DashScope native endpoint.

Note: NOT OpenAI-compatible — uses DashScope Generation API.
"""
from __future__ import annotations

import asyncio
from collections.abc import Sequence

import dashscope
from dashscope import TextReRank

from app.core.config import get_settings
from app.core.retry import retry_async


class RerankClient:
    def __init__(self, model: str = "qwen3-rerank"):
        settings = get_settings()
        dashscope.api_key = settings.dashscope_api_key
        self.model = model
        self.batch_size = 10

    async def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_n: int = 5,
    ) -> list[tuple[int, float]]:
        """Rerank documents by relevance to query.

        Returns list of (original_index, relevance_score), sorted by score desc.
        """
        if not documents:
            return []
        # DashScope TextReRank is sync; run in executor to avoid blocking event loop
        loop = asyncio.get_running_loop()
        results = await retry_async(
            lambda: loop.run_in_executor(None, self._rerank_sync, query, list(documents), top_n),
            max_attempts=3,
            retry_on=(Exception,),
        )
        return results

    def _rerank_sync(self, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        # DashScope SDK returns Response object with .output.results
        resp = TextReRank.call(
            model=self.model,
            query=query,
            documents=documents,
            top_n=min(top_n, len(documents)),
            return_documents=False,
        )
        if getattr(resp, "status_code", 200) != 200:
            raise RuntimeError(f"Rerank failed: {getattr(resp, 'message', 'unknown')}")
        out: list[tuple[int, float]] = []
        for item in resp.output.results:
            out.append((int(item["index"]), float(item["relevance_score"])))
        out.sort(key=lambda x: x[1], reverse=True)
        return out