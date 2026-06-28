from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models import Policy
from app.rag.bm25_index import WhooshIndexManager
from app.rag.chroma_store import ChromaStore
from app.rag.chunker import chunk_text
from app.clients.embedding_client import EmbeddingClient
from app.repositories.policy_repository import PolicyRepository


class PolicyService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        bm25: WhooshIndexManager,
        chroma: ChromaStore,
        embedding: EmbeddingClient,
    ):
        self.session = session
        self.repo = PolicyRepository(session)
        self.bm25 = bm25
        self.chroma = chroma
        self.embedding = embedding

    async def list_all(self, tenant_id: UUID) -> list[Policy]:
        return await self.repo.list_all(tenant_id)

    async def get(self, policy_id: int, tenant_id: UUID) -> Policy:
        policy = await self.repo.get_by_id(policy_id, tenant_id)
        if policy is None:
            raise NotFound(f"Policy {policy_id} not found")
        return policy

    async def create(self, *, tenant_id: UUID, data: dict) -> Policy:
        policy = await self.repo.create(tenant_id=tenant_id, data=data)
        await self._index_policy(tenant_id, policy)
        return policy

    async def update(self, policy_id: int, tenant_id: UUID, data: dict) -> Policy:
        policy = await self.get(policy_id, tenant_id)
        # Remove old chunks
        self._delete_index(tenant_id, str(policy.id))
        updated = await self.repo.update(policy, data)
        await self._index_policy(tenant_id, updated)
        return updated

    async def delete(self, policy_id: int, tenant_id: UUID) -> None:
        policy = await self.get(policy_id, tenant_id)
        self._delete_index(tenant_id, str(policy.id))
        await self.repo.delete(policy)

    async def reindex(self, policy_id: int, tenant_id: UUID) -> Policy:
        policy = await self.get(policy_id, tenant_id)
        self._delete_index(tenant_id, str(policy.id))
        await self._index_policy(tenant_id, policy)
        return policy

    async def _index_policy(self, tenant_id: UUID, policy: Policy) -> None:
        chunks = chunk_text(policy.content)
        if not chunks:
            return
        # BM25
        self.bm25.add_chunks(
            tenant_id,
            [(c.chunk_id, str(policy.id), policy.title, c.content) for c in chunks],
        )
        # ChromaDB (dense)
        vectors = await self.embedding.embed([c.content for c in chunks])
        self.chroma.upsert(
            tenant_id,
            ids=[c.chunk_id for c in chunks],
            embeddings=vectors,
            documents=[c.content for c in chunks],
            metadatas=[
                {"source_id": str(policy.id), "title": policy.title}
                for _ in chunks
            ],
        )
        # Mark indexed_at
        from datetime import datetime, timezone
        policy.indexed_at = datetime.now(timezone.utc)
        await self.session.flush()

    def _delete_index(self, tenant_id: UUID, source_id: str) -> None:
        self.bm25.delete_by_source(tenant_id, source_id)
        self.chroma.delete_by_source(tenant_id, source_id)