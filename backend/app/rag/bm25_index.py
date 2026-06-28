"""Whoosh index manager — one index per tenant, persisted to disk."""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

from whoosh import index
from whoosh.analysis import StemmingAnalyzer
from whoosh.fields import ID, TEXT, Schema
from whoosh.qparser import MultifieldParser

_SCHEMA = Schema(
    chunk_id=ID(stored=True, unique=True),
    tenant_id=ID(stored=True),
    source_id=ID(stored=True),
    title=TEXT(stored=True),
    content=TEXT(stored=True, analyzer=StemmingAnalyzer()),
)


class WhooshIndexManager:
    """Owns Whoosh indexes under a base directory, one subdir per tenant."""

    def __init__(self, base_dir: Path | str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _tenant_dir(self, tenant_id: UUID) -> Path:
        d = self.base_dir / str(tenant_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_index(self, tenant_id: UUID):
        """Open or create the tenant's index."""
        d = self._tenant_dir(tenant_id)
        ix = index.open_dir(str(d)) if index.exists_in(str(d)) else index.create_in(str(d), _SCHEMA)
        return ix

    def add_chunks(
        self,
        tenant_id: UUID,
        chunks: list[tuple[str, str, str, str]],  # (chunk_id, source_id, title, content)
    ) -> None:
        """Bulk-add chunks. chunk_id is the dedup key."""
        ix = self.get_index(tenant_id)
        writer = ix.writer()
        for chunk_id, source_id, title, content in chunks:
            writer.update_document(
                chunk_id=chunk_id,
                tenant_id=str(tenant_id),
                source_id=source_id,
                title=title,
                content=content,
            )
        writer.commit()

    def delete_by_source(self, tenant_id: UUID, source_id: str) -> None:
        """Remove all chunks belonging to a source."""
        ix = self.get_index(tenant_id)
        writer = ix.writer()
        writer.delete_by_term("source_id", source_id)
        writer.commit()

    def search(self, tenant_id: UUID, query: str, top_k: int = 20) -> list[dict]:
        """Search and return list of {chunk_id, source_id, title, content, score}."""
        ix = self.get_index(tenant_id)
        parser = MultifieldParser(["title", "content"], schema=ix.schema)
        parsed = parser.parse(query)
        results: list[dict] = []
        with ix.searcher() as searcher:
            hits = searcher.search(parsed, limit=top_k)
            for hit in hits:
                results.append(
                    {
                        "chunk_id": hit["chunk_id"],
                        "source_id": hit["source_id"],
                        "title": hit.get("title", ""),
                        "content": hit["content"],
                        "score": float(hit.score),
                    }
                )
        return results