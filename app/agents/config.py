"""图书馆聊天配置"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChatConfig:
    """聊天服务运行时配置"""

    model: str = "stub"
    retriever_top_k: int = 5
    max_history_turns: int = 10
    chroma_persist_dir: str = "./chroma_data"
    chroma_collection: str = "library_policies"
