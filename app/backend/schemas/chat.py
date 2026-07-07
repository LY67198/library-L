"""聊天与图书检索请求/响应 Pydantic 模型"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """同步/流式问答请求"""

    query: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = None
    history: list[dict] | None = None


class ChatResponse(BaseModel):
    """同步问答响应"""

    intent: str
    response: str
    sources: list[dict]
    subgraph: str


class BookSearchResult(BaseModel):
    """图书检索结果"""

    id: str
    title: str
    author: str
    isbn: str | None = None
    location: str | None = None
    available: int = 0
