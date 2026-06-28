"""Qwen text-embedding-v2 via DashScope OpenAI-compatible API.

Per spec ADR-006: Chinese-friendly + native.
Per MVP (ADR-001): single embedding model; interface ready for multi-modal later.
"""
from __future__ import annotations

from collections.abc import Sequence

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.retry import retry_async


class EmbeddingClient:
    def __init__(self, model: str = "text-embedding-v2"):
        settings = get_settings()
        # DashScope OpenAI-compatible endpoint
        self.client = AsyncOpenAI(
            api_key=settings.dashscope_api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.model = model
        self.batch_size = 32

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a batch of texts. Auto-splits into chunks of self.batch_size."""
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
        # OpenAI-compatible: input is list[str], data[i].embedding is the vector
        result = await self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in result.data]