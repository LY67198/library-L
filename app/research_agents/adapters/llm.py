from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    def classify_intent(self, query: str) -> str: ...

    def answer_direct(self, query: str, memory_context: str = "") -> str: ...

    def plan_research(self, query: str) -> dict: ...

    def judge_evidence(self, query: str, records: list[dict]) -> list[dict]: ...

    def analyze(self, query: str, evidence: list[dict]) -> dict: ...

    def reflect(self, query: str, missing_gaps: list[str]) -> list[dict]: ...

    def write_report(self, query: str, findings: list[dict], sources: list[dict]) -> str: ...


class RuleBasedLLMClient:
    """Small deterministic adapter so the scaffold works without API keys."""

    def classify_intent(self, query: str) -> str:
        lowered = query.lower()
        research_markers = {
            "research",
            "compare",
            "market",
            "trend",
            "evidence",
            "sources",
            "report",
            "analysis",
            "strategy",
        }
        return "research" if any(marker in lowered for marker in research_markers) else "direct"

    def answer_direct(self, query: str, memory_context: str = "") -> str:
        context = f"\n\nMemory context:\n{memory_context}" if memory_context else ""
        return f"Direct scaffold response for: {query}{context}"

    def plan_research(self, query: str) -> dict:
        return {
            "summary": f"Research plan for: {query}",
            "sub_questions": [
                f"What is the current context for {query}?",
                f"What evidence supports the main claims about {query}?",
                f"What risks or tradeoffs should be considered for {query}?",
            ],
            "search_plan": [
                {"query": query, "source": "hybrid", "reason": "original user question"},
                {"query": f"{query} evidence sources", "source": "web", "reason": "external evidence"},
                {"query": f"{query} internal notes", "source": "local", "reason": "local knowledge"},
            ],
        }

    def judge_evidence(self, query: str, records: list[dict]) -> list[dict]:
        judged = []
        for idx, record in enumerate(records, 1):
            item = dict(record)
            item.setdefault("source_id", f"SRC-{idx}")
            item["relevance_score"] = 0.75
            item["supports"] = [query]
            judged.append(item)
        return judged

    def analyze(self, query: str, evidence: list[dict]) -> dict:
        findings = [
            {
                "claim": f"Initial scaffold finding for: {query}",
                "supporting_source_ids": [item.get("source_id") for item in evidence[:3]],
                "confidence": "medium" if evidence else "low",
            }
        ]
        missing_gaps = [] if evidence else ["No evidence was collected"]
        return {"findings": findings, "missing_gaps": missing_gaps}

    def reflect(self, query: str, missing_gaps: list[str]) -> list[dict]:
        if not missing_gaps:
            return []
        return [
            {
                "query": f"{query} missing evidence",
                "source": "hybrid",
                "reason": "; ".join(missing_gaps),
            }
        ]

    def write_report(self, query: str, findings: list[dict], sources: list[dict]) -> str:
        lines = [f"# Research Result: {query}", ""]
        lines.append("## Findings")
        if findings:
            for idx, finding in enumerate(findings, 1):
                source_ids = ", ".join(str(item) for item in finding.get("supporting_source_ids", []) if item)
                suffix = f" [{source_ids}]" if source_ids else ""
                lines.append(f"{idx}. {finding.get('claim', 'Finding')}{suffix}")
        else:
            lines.append("- No findings were produced.")
        lines.extend(["", "## Sources"])
        if sources:
            for source in sources:
                lines.append(f"- {source.get('source_id')}: {source.get('label')} ({source.get('locator')})")
        else:
            lines.append("- No sources.")
        return "\n".join(lines)

