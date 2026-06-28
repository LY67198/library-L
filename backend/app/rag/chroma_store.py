"""ChromaDB persistent client — one collection per tenant."""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

import chromadb
from chromadb.config import Settings as ChromaSettings


class ChromaStore:
    """Wraps a persistent ChromaDB client; collections are named `library_{tenant_id}`."""

    def __init__(self, persist_dir: Path | str):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
        )

    def collection_name(self, tenant_id: UUID) -> str:
        return f"library_{tenant_id.hex}"

    def get_or_create(self, tenant_id: UUID):
        name = self.collection_name(tenant_id)
        return self.client.get_or_create_collection(
            name=name,
            metadata={"tenant_id": str(tenant_id)},
        )

    def upsert(
        self,
        tenant_id: UUID,
        *,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        coll = self.get_or_create(tenant_id)
        coll.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

    def delete_by_source(self, tenant_id: UUID, source_id: str) -> None:
        coll = self.get_or_create(tenant_id)
        coll.delete(where={"source_id": source_id})

    def query(
        self,
        tenant_id: UUID,
        *,
        query_embedding: list[float],
        top_k: int = 20,
    ) -> list[dict]:
        coll = self.get_or_create(tenant_id)
        results = coll.query(query_embeddings=[query_embedding], n_results=top_k)
        hits: list[dict] = []
        # ChromaDB returns parallel arrays; transpose
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        for i, chunk_id in enumerate(ids):
            hits.append(
                {
                    "chunk_id": chunk_id,
                    "content": docs[i] if i < len(docs) else "",
                    "source_id": (metas[i] or {}).get("source_id", ""),
                    "title": (metas[i] or {}).get("title", ""),
                    "score": 1.0 - distances[i] if i < len(distances) else 0.0,  # cosine distance → similarity
                }
            )
        return hits
