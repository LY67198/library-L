"""ChromaDB 向量检索器 — 政策文档语义搜索"""

from __future__ import annotations


class ChromaDBRetriever:
    """基于 ChromaDB 的政策文档向量检索器"""

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
