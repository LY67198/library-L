from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class ResearchState(TypedDict):
    query: str
    user_id: str
    tenant_id: str
    memory_context: str
    messages: Annotated[list[str], operator.add]
    intent: str
    phase: str
    plan: str
    sub_questions: list[str]
    search_plan: list[dict]
    web_evidence: list[dict]
    local_evidence: list[dict]
    evidence_pool: list[dict]
    findings: list[dict]
    missing_gaps: list[str]
    supplementary_queries: list[dict]
    source_index: list[dict]
    draft: str
    final: str
    iteration: int
    max_iterations: int


def create_initial_state(
    query: str,
    user_id: str,
    tenant_id: str,
    max_iterations: int,
    memory_context: str = "",
) -> ResearchState:
    return {
        "query": query,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "memory_context": memory_context,
        "messages": [],
        "intent": "",
        "phase": "initialized",
        "plan": "",
        "sub_questions": [],
        "search_plan": [],
        "web_evidence": [],
        "local_evidence": [],
        "evidence_pool": [],
        "findings": [],
        "missing_gaps": [],
        "supplementary_queries": [],
        "source_index": [],
        "draft": "",
        "final": "",
        "iteration": 0,
        "max_iterations": max_iterations,
    }

