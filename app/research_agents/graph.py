from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .nodes import (
    NodeContext,
    analyze_node,
    direct_answer_node,
    evidence_judge_node,
    intent_node,
    local_rag_node,
    plan_node,
    reflect_node,
    web_search_node,
    write_node,
)
from .state import ResearchState


def build_graph(context: NodeContext):
    graph = StateGraph(ResearchState)
    graph.add_node("intent", lambda state: intent_node(state, context))
    graph.add_node("direct_answer", lambda state: direct_answer_node(state, context))
    graph.add_node("plan", lambda state: plan_node(state, context))
    graph.add_node("web_search", lambda state: web_search_node(state, context))
    graph.add_node("local_rag", lambda state: local_rag_node(state, context))
    graph.add_node("evidence_judge", lambda state: evidence_judge_node(state, context))
    graph.add_node("analyze", lambda state: analyze_node(state, context))
    graph.add_node("reflect", lambda state: reflect_node(state, context))
    graph.add_node("write", lambda state: write_node(state, context))

    graph.add_edge(START, "intent")
    graph.add_conditional_edges(
        "intent",
        _route_after_intent,
        {
            "direct": "direct_answer",
            "research": "plan",
        },
    )
    graph.add_edge("plan", "web_search")
    graph.add_edge("plan", "local_rag")
    graph.add_edge("web_search", "evidence_judge")
    graph.add_edge("local_rag", "evidence_judge")
    graph.add_edge("evidence_judge", "analyze")
    graph.add_conditional_edges(
        "analyze",
        _route_after_analysis,
        {
            "reflect": "reflect",
            "write": "write",
        },
    )
    graph.add_edge("reflect", "web_search")
    graph.add_edge("reflect", "local_rag")
    graph.add_edge("direct_answer", END)
    graph.add_edge("write", END)
    return graph.compile()


def _route_after_intent(state: ResearchState) -> str:
    return "direct" if state.get("intent") == "direct" else "research"


def _route_after_analysis(state: ResearchState) -> str:
    if state.get("missing_gaps") and state.get("iteration", 0) < state.get("max_iterations", 1):
        return "reflect"
    return "write"

