"""ChromaDB 持久化客户端 — 每个租户一个 collection。"""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

import chromadb
from chromadb.config import Settings as ChromaSettings


class ChromaStore:
    """ChromaDB 存储封装 — collection 命名规则为 `library_{tenant_id}`。"""

    def __init__(self, persist_dir: Path | str):
        """初始化 ChromaStore。

        参数:
            persist_dir: ChromaDB 数据持久化目录。
        """
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
        )

    def collection_name(self, tenant_id: UUID) -> str:
        """生成租户对应的 collection 名。

        参数:
            tenant_id: 租户 UUID。

        返回值:
            str: collection 名称,格式为 `library_{tenant_id.hex}`。
        """
        return f"library_{tenant_id.hex}"

    def get_or_create(self, tenant_id: UUID):
        """获取或创建租户对应的 collection。

        参数:
            tenant_id: 租户 UUID。

        返回值:
            chromadb.api.models.Collection: 对应租户的 collection 实例。
        """
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
        """向租户 collection 写入或更新向量与文档。

        参数:
            tenant_id: 租户 UUID。
            ids: chunk ID 列表(与其它字段一一对应)。
            embeddings: 与 ids 对应的向量列表。
            documents: 原始文档文本列表。
            metadatas: 元数据字典列表。

        返回值:
            None: 无返回值。
        """
        coll = self.get_or_create(tenant_id)
        coll.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

    def delete_by_source(self, tenant_id: UUID, source_id: str) -> None:
        """删除指定 source 的全部记录。

        参数:
            tenant_id: 租户 UUID。
            source_id: 文档/数据源 ID。

        返回值:
            None: 无返回值。
        """
        coll = self.get_or_create(tenant_id)
        coll.delete(where={"source_id": source_id})

    def query(
        self,
        tenant_id: UUID,
        *,
        query_embedding: list[float],
        top_k: int = 20,
    ) -> list[dict]:
        """在租户 collection 中按向量相似度检索。

        参数:
            tenant_id: 租户 UUID。
            query_embedding: 查询向量。
            top_k: 返回的最大命中数,默认 20。

        返回值:
            list[dict]: 命中列表,字段包含 `chunk_id`、`content`、`source_id`、`title`、`score`(将 cosine 距离转换为相似度)。
        """
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
