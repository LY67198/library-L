"""Qwen text-embedding-v2 Embedding 客户端 — 基于 DashScope OpenAI 兼容 API。

依据 ADR-006:中文友好 + 国产化。
依据 MVP(ADR-001):MVP 阶段单一 embedding 模型,接口预留多模态扩展点。
"""
from __future__ import annotations

from collections.abc import Sequence

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.retry import retry_async


class EmbeddingClient:
    """Embedding 客户端 — 调用 DashScope OpenAI 兼容端点获取文本向量。"""

    def __init__(self, model: str = "text-embedding-v2"):
        """初始化 EmbeddingClient。

        参数:
            model: 使用的 embedding 模型名称,默认 `text-embedding-v2`。
        """
        settings = get_settings()
        # DashScope OpenAI-compatible endpoint
        self.client = AsyncOpenAI(
            api_key=settings.dashscope_api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.model = model
        self.batch_size = 32

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """将一批文本向量化。自动按 `self.batch_size` 切片请求。

        参数:
            texts: 待向量化的文本序列。

        返回值:
            list[list[float]]: 与输入等长的向量列表,顺序一致。
        """
        if not texts:
            return []
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            chunk = list(texts[i : i + self.batch_size])
            response = await retry_async(
                lambda c=chunk: self._embed_once(c),
                max_attempts=3,
                retry_on=(Exception,),
            )
            out.extend(response)
        return out

    async def _embed_once(self, texts: list[str]) -> list[list[float]]:
        """单批 embedding 调用,内部使用,带 OpenAI 兼容解析。

        参数:
            texts: 单批文本(不超过 `self.batch_size`)。

        返回值:
            list[list[float]]: 该批文本对应的向量列表。
        """
        # OpenAI-compatible: input is list[str], data[i].embedding is the vector
        result = await self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in result.data]