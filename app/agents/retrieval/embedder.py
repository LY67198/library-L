"""Qwen 文本嵌入客户端 — DashScope text-embedding-v2, 1024d"""

from __future__ import annotations

import logging
from typing import Any

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)

# DashScope 兼容 OpenAI 接口格式
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class QwenEmbedder:
    """Qwen text-embedding-v2 嵌入客户端

    调用 DashScope 开放 API 生成 1024 维文本向量。
    """

    def __init__(self, api_key: str = "", model: str = ""):
        settings = get_settings()
        self._api_key = api_key or getattr(settings, "dashscope_api_key", "") or ""
        self._model = model or getattr(settings, "embedding_model", "text-embedding-v2")
        self._client: Any = None

    def _ensure_client(self):
        if self._client is not None:
            return
        if not self._api_key:
            raise RuntimeError("DashScope API Key 未配置，请在 .env 中设置 DASHSCOPE_API_KEY")
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai SDK 未安装，请执行: uv add openai")
        self._client = OpenAI(api_key=self._api_key, base_url=DASHSCOPE_BASE_URL)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入，返回 1024d 向量列表"""
        if not texts:
            return []
        self._ensure_client()
        try:
            response = self._client.embeddings.create(
                model=self._model,
                input=texts,
            )
            return [d.embedding for d in response.data]
        except Exception as exc:
            logger.error(f"嵌入调用失败: {exc}")
            raise RuntimeError(f"嵌入调用失败: {exc}")

    def embed_single(self, text: str) -> list[float]:
        """单个文本嵌入"""
        results = self.embed([text])
        return results[0] if results else []
