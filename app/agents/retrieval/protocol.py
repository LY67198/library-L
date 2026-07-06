"""Retriever Protocol — 检索器扩展点，与 LLMClient 同级别"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Retriever(Protocol):
    """检索器协议接口

    任何实现了 search(query, top_k, **kwargs) -> list[dict] 的对象
    都可以作为检索器注入到 Agent 中。
    """

    def search(self, query: str, top_k: int = 5, **kwargs) -> list[dict]:
        """检索并返回结果列表

        返回格式: [{"content": "...", "metadata": {...}, "score": 0.95}, ...]
        """
        ...


class StubRetriever:
    """确定性桩检索器 — 无需外部依赖即可运行，返回占位结果"""

    def search(self, query: str, top_k: int = 5, **kwargs) -> list[dict]:
        return [
            {
                "content": f"Placeholder result {idx} for: {query}",
                "metadata": {"source": f"stub-{idx}"},
                "score": 0.9 - idx * 0.1,
            }
            for idx in range(1, min(top_k, 3) + 1)
        ]
