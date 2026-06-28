"""政策领域服务 — 政策 CRUD,自动维护 BM25 + ChromaDB 双引擎索引。"""
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
    """馆内政策领域服务,负责政策 CRUD 以及 BM25 + ChromaDB 双重索引的维护。

    双重索引策略:
        - BM25(Whoosh):负责稀疏关键词检索,覆盖专有名词、馆内术语等精确匹配场景;
        - ChromaDB(稠密向量):负责语义检索,覆盖改写、口语化提问场景。
        两路结果在检索阶段通过 RRF 融合。任一索引变更都必须同步另一路以避免漏召。

    重新索引流程(reindex):
        1. 先删除该政策在 BM25 与 ChromaDB 中的全部旧分块;
        2. 重新分块并写入两份索引;
        3. 更新 indexed_at 时间戳。
        该流程在外部文档语料或切分策略变更后用于全量刷新,保证两边索引一致。
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        bm25: WhooshIndexManager,
        chroma: ChromaStore,
        embedding: EmbeddingClient,
    ):
        """初始化服务实例。

        参数:
            session: SQLAlchemy 异步会话
            bm25: Whoosh BM25 索引管理器
            chroma: ChromaDB 稠密向量存储
            embedding: Embedding 客户端,用于生成向量
        """
        self.session = session
        self.repo = PolicyRepository(session)
        self.bm25 = bm25
        self.chroma = chroma
        self.embedding = embedding

    async def list_all(self, tenant_id: UUID) -> list[Policy]:
        """列出指定租户的全部政策。

        参数:
            tenant_id: 所属租户 ID

        返回值:
            list[Policy]: 政策列表
        """
        return await self.repo.list_all(tenant_id)

    async def get(self, policy_id: int, tenant_id: UUID) -> Policy:
        """按主键查询单条政策。

        参数:
            policy_id: 政策主键 ID
            tenant_id: 所属租户 ID

        返回值:
            Policy: 政策对象

        抛出:
            NotFound: 政策不存在
        """
        policy = await self.repo.get_by_id(policy_id, tenant_id)
        if policy is None:
            raise NotFound(f"Policy {policy_id} not found")
        return policy

    async def create(self, *, tenant_id: UUID, data: dict) -> Policy:
        """创建政策并在 BM25 + ChromaDB 中建立双重索引。

        参数:
            tenant_id: 所属租户 ID
            data: 政策字段字典,需至少包含 title 与 content

        返回值:
            Policy: 已建索引的政策对象
        """
        policy = await self.repo.create(tenant_id=tenant_id, data=data)
        await self._index_policy(tenant_id, policy)
        return policy

    async def update(self, policy_id: int, tenant_id: UUID, data: dict) -> Policy:
        """更新政策字段,先删除旧索引再重新建立双重索引。

        参数:
            policy_id: 政策主键 ID
            tenant_id: 所属租户 ID
            data: 待更新字段字典

        返回值:
            Policy: 更新后并已重新建索引的政策对象

        抛出:
            NotFound: 政策不存在
        """
        policy = await self.get(policy_id, tenant_id)
        # 先清理 BM25 与 ChromaDB 中的旧分块
        self._delete_index(tenant_id, str(policy.id))
        updated = await self.repo.update(policy, data)
        await self._index_policy(tenant_id, updated)
        return updated

    async def delete(self, policy_id: int, tenant_id: UUID) -> None:
        """删除政策并同时清理 BM25 + ChromaDB 中的索引。

        参数:
            policy_id: 政策主键 ID
            tenant_id: 所属租户 ID

        抛出:
            NotFound: 政策不存在
        """
        policy = await self.get(policy_id, tenant_id)
        self._delete_index(tenant_id, str(policy.id))
        await self.repo.delete(policy)

    async def reindex(self, policy_id: int, tenant_id: UUID) -> Policy:
        """强制对单条政策重新执行完整的双重索引流程。

        适用于:
            - 切分策略或 Embedding 模型升级后,需要清空旧向量重新生成;
            - 索引出现数据漂移后的修复。

        参数:
            policy_id: 政策主键 ID
            tenant_id: 所属租户 ID

        返回值:
            Policy: 已重新索引的政策对象

        抛出:
            NotFound: 政策不存在
        """
        policy = await self.get(policy_id, tenant_id)
        self._delete_index(tenant_id, str(policy.id))
        await self._index_policy(tenant_id, policy)
        return policy

    async def _index_policy(self, tenant_id: UUID, policy: Policy) -> None:
        """对单条政策执行 BM25 + ChromaDB 的双重写入。

        步骤:
            1. 调用 chunk_text 将政策正文切分为若干分块;
            2. 将分块写入 Whoosh BM25 索引;
            3. 调用 Embedding 客户端得到向量后写入 ChromaDB;
            4. 更新政策的 indexed_at 时间戳。

        参数:
            tenant_id: 所属租户 ID
            policy: 已持久化的政策 ORM 实例
        """
        chunks = chunk_text(policy.content)
        if not chunks:
            return
        # BM25 关键词索引
        self.bm25.add_chunks(
            tenant_id,
            [(c.chunk_id, str(policy.id), policy.title, c.content) for c in chunks],
        )
        # ChromaDB 稠密向量索引
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
        # 更新索引时间戳
        from datetime import datetime, timezone
        policy.indexed_at = datetime.now(timezone.utc)
        await self.session.flush()

    def _delete_index(self, tenant_id: UUID, source_id: str) -> None:
        """从 BM25 与 ChromaDB 中按 source_id 删除指定政策的全部分块。

        参数:
            tenant_id: 所属租户 ID
            source_id: 政策主键(字符串形式)
        """
        self.bm25.delete_by_source(tenant_id, source_id)
        self.chroma.delete_by_source(tenant_id, source_id)