from __future__ import annotations

from dataclasses import dataclass

from .adapters.llm import LLMClient
from .config import ResearchConfig
from .memory.store import MemoryStore
from .state import ResearchState
from .tools import SearchTools


@dataclass(frozen=True)
class NodeContext:
    config: ResearchConfig
    llm: LLMClient
    tools: SearchTools
    memory: MemoryStore


def intent_node(state: ResearchState, context: NodeContext) -> ResearchState:
    intent = context.llm.classify_intent(state["query"])
    return {
        "intent": intent,
        "phase": "intent classified",
        "messages": [f"intent={intent}"],
    }


def direct_answer_node(state: ResearchState, context: NodeContext) -> ResearchState:
    answer = context.llm.answer_direct(state["query"], memory_context=state.get("memory_context", ""))
    return {
        "phase": "direct answer completed",
        "final": answer,
        "draft": answer,
        "messages": [answer],
    }


def plan_node(state: ResearchState, context: NodeContext) -> ResearchState:
    plan = context.llm.plan_research(state["query"])
    sub_questions = plan.get("sub_questions", [state["query"]])
    search_plan = plan.get("search_plan", [{"query": state["query"], "source": "hybrid"}])
    return {
        "phase": "planning completed",
        "plan": plan.get("summary", state["query"]),
        "sub_questions": sub_questions,
        "search_plan": search_plan,
        "messages": [f"planned {len(search_plan)} search steps"],
    }


def web_search_node(state: ResearchState, context: NodeContext) -> ResearchState:
    if not context.config.web_search_enabled:
        return {"web_evidence": [], "messages": ["web search disabled"]}
    records = []
    for item in _queries_for_source(state, "web"):
        records.extend(context.tools.search_web(str(item.get("query", "")), limit=4))
    return {
        "web_evidence": _dedupe(records, "url"),
        "messages": [f"web evidence={len(records)}"],
    }


def local_rag_node(state: ResearchState, context: NodeContext) -> ResearchState:
    if not context.config.local_rag_enabled:
        return {"local_evidence": [], "messages": ["local rag disabled"]}
    records = []
    for item in _queries_for_source(state, "local"):
        records.extend(context.tools.search_local(str(item.get("query", "")), limit=4))
    return {
        "local_evidence": _dedupe(records, "doc_id"),
        "messages": [f"local evidence={len(records)}"],
    }


def evidence_judge_node(state: ResearchState, context: NodeContext) -> ResearchState:
    raw = state.get("web_evidence", []) + state.get("local_evidence", [])
    evidence_pool = context.llm.judge_evidence(state["query"], raw)
    source_index = [
        {
            "source_id": item.get("source_id", f"SRC-{idx}"),
            "label": item.get("title", item.get("source_id", f"Source {idx}")),
            "locator": item.get("url") or item.get("doc_id") or "",
        }
        for idx, item in enumerate(evidence_pool, 1)
    ]
    return {
        "phase": "evidence judged",
        "evidence_pool": evidence_pool,
        "source_index": source_index,
        "messages": [f"evidence pool={len(evidence_pool)}"],
    }


def analyze_node(state: ResearchState, context: NodeContext) -> ResearchState:
    analysis = context.llm.analyze(state["query"], state.get("evidence_pool", []))
    return {
        "phase": "analysis completed",
        "findings": analysis.get("findings", []),
        "missing_gaps": analysis.get("missing_gaps", []),
        "messages": [f"findings={len(analysis.get('findings', []))}"],
    }


def reflect_node(state: ResearchState, context: NodeContext) -> ResearchState:
    follow_up = context.llm.reflect(state["query"], state.get("missing_gaps", []))
    return {
        "phase": "reflection completed",
        "iteration": state.get("iteration", 0) + 1,
        "supplementary_queries": follow_up,
        "search_plan": follow_up,
        "missing_gaps": [],
        "messages": [f"follow-up queries={len(follow_up)}"],
    }


def write_node(state: ResearchState, context: NodeContext) -> ResearchState:
    final = context.llm.write_report(
        query=state["query"],
        findings=state.get("findings", []),
        sources=state.get("source_index", []),
    )
    return {
        "phase": "write completed",
        "draft": final,
        "final": final,
        "messages": ["final report written"],
    }


def _queries_for_source(state: ResearchState, source: str) -> list[dict]:
    queries = state.get("supplementary_queries") or state.get("search_plan") or [{"query": state["query"]}]
    selected = []
    for item in queries:
        item_source = str(item.get("source", item.get("source_preference", "hybrid")))
        if item_source in {source, "hybrid"}:
            selected.append(item)
    return selected or [{"query": state["query"], "source": source}]


def _dedupe(records: list[dict], key: str) -> list[dict]:
    seen = set()
    result = []
    for record in records:
        marker = str(record.get(key) or record.get("title") or record)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(record)
    return result
