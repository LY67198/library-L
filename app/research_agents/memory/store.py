from __future__ import annotations

from collections import defaultdict
from typing import Protocol


class MemoryStore(Protocol):
    def build_context(self, tenant_id: str, user_id: str, thread_id: str, query: str, limit: int) -> str: ...

    def persist_turn(self, tenant_id: str, user_id: str, thread_id: str, query: str, answer: str) -> None: ...


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self._turns: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)

    def build_context(self, tenant_id: str, user_id: str, thread_id: str, query: str, limit: int) -> str:
        key = (tenant_id, user_id, thread_id)
        turns = self._turns.get(key, [])[-limit:]
        if not turns:
            return ""
        lines = []
        for previous_query, previous_answer in turns:
            lines.append(f"User: {previous_query}")
            lines.append(f"Assistant: {previous_answer[:500]}")
        return "\n".join(lines)

    def persist_turn(self, tenant_id: str, user_id: str, thread_id: str, query: str, answer: str) -> None:
        key = (tenant_id, user_id, thread_id)
        self._turns[key].append((query, answer))

