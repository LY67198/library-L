"""ChromaDB 向量检索器 — 政策文档语义搜索 + 写入/删除"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ChromaDBRetriever:
    """基于 ChromaDB 的政策文档向量检索器，支持搜索、写入和按文档 ID 删除"""

    def __init__(self, collection_name: str = "library_policies", persist_dir: str = "./chroma_data"):
        self._collection_name = collection_name
        self._persist_dir = persist_dir
        self._client = None
        self._collection = None

    def _ensure_initialized(self):
        if self._collection is not None:
            return
        try:
            import chromadb
            from chromadb.config import Settings

            self._client = chromadb.PersistentClient(
                path=self._persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
            )
        except ImportError:
            raise RuntimeError("chromadb 未安装，请执行: uv add chromadb")
        except Exception as exc:
            raise RuntimeError(f"ChromaDB 连接失败: {exc}")

    def search(self, query: str, top_k: int = 5, **kwargs) -> list[dict]:
        """向量检索政策文档，返回排序后的结果列表"""
        try:
            self._ensure_initialized()
            assert self._collection is not None
            results = self._collection.query(
                query_texts=[query],
                n_results=top_k,
            )
            docs = []
            if results.get("documents") and results["documents"][0]:
                for idx, doc in enumerate(results["documents"][0]):
                    meta = {}
                    if results.get("metadatas") and results["metadatas"][0]:
                        meta = results["metadatas"][0][idx] or {}
                    score = 1.0
                    if results.get("distances") and results["distances"][0]:
                        dist = results["distances"][0][idx]
                        score = 1.0 / (1.0 + dist) if dist is not None else 1.0
                    docs.append({"content": doc, "metadata": meta, "score": score})
            return docs
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"ChromaDB 检索失败: {exc}")

    def add_documents(self, chunks: list[dict]):
        """写入 chunks 到 collection

        每个 chunk 格式: {"id": "doc_uuid_0", "document": "文本...", "metadata": {...}}
        使用 upsert，支持覆盖已有文档的重新索引。
        """
        if not chunks:
            return
        self._ensure_initialized()
        assert self._collection is not None
        try:
            ids = [c["id"] for c in chunks]
            documents = [c["document"] for c in chunks]
            metadatas = [c.get("metadata", {}) for c in chunks]
            self._collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"ChromaDB 写入失败: {exc}")

    def delete_by_doc_id(self, doc_id: str):
        """按 doc_id 删除对应 chunks"""
        self._ensure_initialized()
        assert self._collection is not None
        try:
            existing = self._collection.get(where={"doc_id": doc_id})
            if existing and existing.get("ids"):
                self._collection.delete(ids=existing["ids"])
        except Exception:
            # ChromaDB where 过滤可能失败（旧版本/无 metadata），降级为遍历匹配
            logger.warning("ChromaDB where 过滤失败，尝试遍历匹配删除 doc_id=%s", doc_id)
            try:
                all_items = self._collection.get()
                if all_items and all_items.get("ids"):
                    matched_ids = []
                    metadatas = all_items.get("metadatas") or []
                    for i, item_id in enumerate(all_items["ids"]):
                        meta = metadatas[i] if i < len(metadatas) else {}
                        if meta.get("doc_id") == doc_id:
                            matched_ids.append(item_id)
                    if matched_ids:
                        self._collection.delete(ids=matched_ids)
            except Exception as fallback_exc:
                logger.warning("ChromaDB 降级删除也失败 doc_id=%s: %s", doc_id, fallback_exc)
