"""Qwen qwen3-rerank Rerank 客户端 — 基于 DashScope 原生端点。

注意:非 OpenAI 兼容协议,使用 DashScope 专用 Generation API。
"""
from __future__ import annotations

import asyncio
from collections.abc import Sequence

import dashscope
from dashscope import TextReRank

from app.core.config import get_settings
from app.core.retry import retry_async


class RerankClient:
    """Rerank 客户端 — 调用 DashScope 原生 TextReRank 端点对候选文档重排。"""

    def __init__(self, model: str = "qwen3-rerank"):
        """初始化 RerankClient。

        参数:
            model: 使用的 rerank 模型名称,默认 `qwen3-rerank`。
        """
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
        """根据 query 对 documents 重排。

        参数:
            query: 查询字符串。
            documents: 候选文档文本序列。
            top_n: 返回前 N 个结果,默认 5。

        返回值:
            list[tuple[int, float]]: `(原始索引, 相关性分数)` 列表,按分数降序。
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
        """同步调用 DashScope TextReRank,内部使用。

        参数:
            query: 查询字符串。
            documents: 候选文档文本列表。
            top_n: 返回前 N 个结果。

        返回值:
            list[tuple[int, float]]: `(原始索引, 相关性分数)` 列表,按分数降序。
        """
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