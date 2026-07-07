"""图书馆聊天服务 — 组装 Agent 图 + SSE 流式桥接"""

from __future__ import annotations

import asyncio
from threading import Lock, Thread
from typing import AsyncIterator

from agents.llm import RuleBasedLLMClient
from agents.llm_client import RealLLMClient
from backend.config.settings import get_settings
from openai import OpenAI
from agents.config import ChatConfig
from agents.graph import build_library_graph
from agents.nodes import LibraryNodeContext
from agents.retrieval.protocol import StubRetriever
from agents.state import create_initial_library_state
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def _create_llm_client():
    """工厂：API Key 存在时创建 RealLLMClient，否则回退 RuleBasedLLMClient"""
    settings = get_settings()
    if settings.minimax_api_key and settings.deepseek_api_key:
        try:
            primary = OpenAI(
                api_key=settings.minimax_api_key,
                base_url=settings.minimax_base_url,
            )
            secondary = OpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            )
            return RealLLMClient(
                primary_client=primary,
                primary_model=settings.minimax_model,
                secondary_client=secondary,
                secondary_model=settings.deepseek_model,
                fallback=RuleBasedLLMClient(),
            )
        except Exception:
            pass  # 配置有问题，回退规则引擎
    return RuleBasedLLMClient()


class ChatService:
    """图书馆聊天服务 — 懒初始化 + 线程安全"""

    def __init__(self):
        self._lock = Lock()
        self._initialized = False
        self._app = None
        self._config = ChatConfig()
        self._session_factory = None

    def set_session_factory(self, factory) -> None:
        """注入 async session factory，供 ProfileService 使用"""
        self._session_factory = factory

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            context = LibraryNodeContext(
                config=self._config,
                llm=_create_llm_client(),
                retriever=StubRetriever(),
                book_lookup=StubRetriever(),
                session_factory=self._session_factory,
            )
            self._app = build_library_graph(context)
            self._initialized = True

    def _invoke_sync(self, query: str, user_id: str | None, history: list[dict] | None) -> dict:
        self._ensure_initialized()
        state = create_initial_library_state(
            query=query,
            user_id=user_id,
            chat_history=history,
        )
        result = self._app.invoke(state)
        return {
            "intent": result.get("intent", "other"),
            "response": result.get("response", ""),
            "sources": result.get("sources", []),
            "subgraph": result.get("subgraph", "direct"),
        }

    def _invoke_sync_stream(self, query: str, user_id: str | None, history: list[dict] | None, emit) -> dict:
        self._ensure_initialized()
        state = create_initial_library_state(
            query=query,
            user_id=user_id,
            chat_history=history,
        )
        for update in self._app.stream(state, stream_mode="updates"):
            if not isinstance(update, dict):
                continue
            for node_name, node_output in update.items():
                if isinstance(node_output, dict):
                    if node_output.get("intent"):
                        emit({"type": "intent", "data": node_output["intent"]})
                    if node_output.get("response"):
                        content = node_output["response"]
                        # 模拟逐字流式输出
                        for i in range(0, len(content), 3):
                            emit({"type": "token", "content": content[i:i + 3]})
                        emit({
                            "type": "done",
                            "intent": node_output.get("intent", "other"),
                            "response": content,
                            "sources": node_output.get("sources", []),
                        })
        return {"intent": "other", "response": "", "sources": []}

    async def chat(
        self,
        query: str,
        user_id: str | None = None,
        history: list[dict] | None = None,
    ) -> dict:
        """同步问答"""
        return await asyncio.to_thread(self._invoke_sync, query, user_id, history)

    async def chat_stream(
        self,
        query: str,
        user_id: str | None = None,
        history: list[dict] | None = None,
    ) -> AsyncIterator[dict]:
        """SSE 流式问答"""
        queue: asyncio.Queue[dict] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def emit(event: dict) -> None:
            asyncio.run_coroutine_threadsafe(queue.put(event), loop)

        def worker() -> None:
            try:
                self._invoke_sync_stream(query, user_id, history, emit)
            except Exception as exc:
                emit({"type": "error", "code": "internal", "message": str(exc)})
            finally:
                emit({"type": "__done__"})

        Thread(target=worker, daemon=True).start()
        while True:
            event = await queue.get()
            if event.get("type") == "__done__":
                break
            yield event


_CHAT_SERVICE: ChatService | None = None


def get_chat_service() -> ChatService:
    """全局单例 — 懒初始化"""
    global _CHAT_SERVICE
    if _CHAT_SERVICE is None:
        _CHAT_SERVICE = ChatService()
        try:
            settings = get_settings()
            engine = create_async_engine(settings.database_url, echo=False)
            _CHAT_SERVICE.set_session_factory(
                async_sessionmaker(engine, expire_on_commit=False)
            )
        except Exception:
            pass
    return _CHAT_SERVICE
