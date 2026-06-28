from __future__ import annotations

import asyncio
from threading import Lock, Thread
from typing import AsyncIterator

from backend.config.settings import AppSettings
from backend.schemas.research import ResearchRequest
from research_agents.config import ResearchConfig
from research_agents.graph import build_graph
from research_agents.memory.store import InMemoryMemoryStore
from research_agents.nodes import NodeContext
from research_agents.state import create_initial_state
from research_agents.tools import SearchTools
from research_agents.adapters.llm import RuleBasedLLMClient


class WorkflowService:
    def __init__(self, config_path: str):
        self._config_path = config_path
        self._lock = Lock()
        self._initialized = False
        self._config: ResearchConfig | None = None
        self._app = None
        self._memory = InMemoryMemoryStore()

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            self._config = ResearchConfig.from_file(self._config_path)
            context = NodeContext(
                config=self._config,
                llm=RuleBasedLLMClient(),
                tools=SearchTools(),
                memory=self._memory,
            )
            self._app = build_graph(context)
            self._initialized = True

    def _run_sync(self, payload: ResearchRequest) -> tuple[str, str]:
        self._ensure_initialized()
        assert self._config is not None
        assert self._app is not None

        max_iterations = payload.max_iterations or self._config.max_iterations
        enable_memory = self._resolve_enable_memory(payload)
        memory_context = ""
        if enable_memory:
            memory_context = self._memory.build_context(
                tenant_id=payload.tenant_id,
                user_id=payload.user_id,
                thread_id=payload.thread_id,
                query=payload.query,
                limit=self._config.memory_top_k,
            )

        state = create_initial_state(
            query=payload.query,
            user_id=payload.user_id,
            tenant_id=payload.tenant_id,
            memory_context=memory_context,
            max_iterations=max_iterations,
        )
        result = self._app.invoke(
            state,
            {"configurable": {"thread_id": payload.thread_id}},
        )
        final = str(result.get("final") or "")
        route = str(result.get("intent") or "research")
        if enable_memory:
            self._memory.persist_turn(
                tenant_id=payload.tenant_id,
                user_id=payload.user_id,
                thread_id=payload.thread_id,
                query=payload.query,
                answer=final,
            )
        return final, route

    def _run_sync_with_events(self, payload: ResearchRequest, emit) -> tuple[str, str]:
        self._ensure_initialized()
        assert self._config is not None
        assert self._app is not None

        max_iterations = payload.max_iterations or self._config.max_iterations
        enable_memory = self._resolve_enable_memory(payload)
        memory_context = ""
        if enable_memory:
            memory_context = self._memory.build_context(
                tenant_id=payload.tenant_id,
                user_id=payload.user_id,
                thread_id=payload.thread_id,
                query=payload.query,
                limit=self._config.memory_top_k,
            )
        state = create_initial_state(
            query=payload.query,
            user_id=payload.user_id,
            tenant_id=payload.tenant_id,
            memory_context=memory_context,
            max_iterations=max_iterations,
        )

        final = ""
        route = "research"
        config = {"configurable": {"thread_id": payload.thread_id}}
        for update in self._app.stream(state, config, stream_mode="updates"):
            if not isinstance(update, dict):
                continue
            for node_name, node_output in update.items():
                emit({"type": "phase", "node": str(node_name), "message": _node_message(str(node_name))})
                if isinstance(node_output, dict):
                    if node_output.get("intent"):
                        route = str(node_output["intent"])
                    if node_output.get("final"):
                        final = str(node_output["final"])
        if enable_memory and final:
            self._memory.persist_turn(
                tenant_id=payload.tenant_id,
                user_id=payload.user_id,
                thread_id=payload.thread_id,
                query=payload.query,
                answer=final,
            )
        return final, route

    def _resolve_enable_memory(self, payload: ResearchRequest) -> bool:
        assert self._config is not None
        if payload.enable_memory is not None:
            return payload.enable_memory
        return self._config.enable_memory

    async def run(self, payload: ResearchRequest) -> str:
        final, _route = await asyncio.to_thread(self._run_sync, payload)
        return final

    async def stream_events(self, payload: ResearchRequest) -> AsyncIterator[dict]:
        queue: asyncio.Queue[dict] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def emit(event: dict) -> None:
            asyncio.run_coroutine_threadsafe(queue.put(event), loop)

        def worker() -> None:
            try:
                final, route = self._run_sync_with_events(payload, emit)
                emit({"type": "route", "message": route})
                emit({"type": "final", "final": final})
            except Exception as exc:
                emit({"type": "error", "message": str(exc)})
            finally:
                emit({"type": "__done__"})

        Thread(target=worker, daemon=True).start()
        while True:
            event = await queue.get()
            if event.get("type") == "__done__":
                break
            yield event


def _node_message(node_name: str) -> str:
    mapping = {
        "intent": "classifying request",
        "direct_answer": "building direct answer",
        "plan": "planning research",
        "web_search": "collecting web evidence",
        "local_rag": "collecting local evidence",
        "evidence_judge": "judging evidence",
        "analyze": "analyzing findings",
        "reflect": "planning follow-up search",
        "write": "writing final report",
    }
    return mapping.get(node_name, f"running {node_name}")


_SERVICE: WorkflowService | None = None


def get_workflow_service() -> WorkflowService:
    global _SERVICE
    if _SERVICE is None:
        settings = AppSettings()
        _SERVICE = WorkflowService(settings.config_path)
    return _SERVICE

