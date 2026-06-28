from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SearchTools:
    """Default stub tools.

    Replace these methods with real web search, vector search, database lookup,
    document parsing, or any domain-specific retrieval implementation.
    """

    def search_web(self, query: str, limit: int = 5) -> list[dict]:
        if not query.strip():
            return []
        return [
            {
                "source_id": f"WEB-{idx}",
                "source_type": "web",
                "title": f"Stub web source {idx}: {query}",
                "url": f"https://example.com/research/{idx}",
                "snippet": f"Placeholder web evidence for: {query}",
            }
            for idx in range(1, min(limit, 3) + 1)
        ]

    def search_local(self, query: str, limit: int = 5) -> list[dict]:
        if not query.strip():
            return []
        return [
            {
                "source_id": f"LOC-{idx}",
                "source_type": "local",
                "title": f"Stub local document {idx}",
                "doc_id": f"doc-{idx}",
                "snippet": f"Placeholder local knowledge for: {query}",
            }
            for idx in range(1, min(limit, 2) + 1)
        ]

