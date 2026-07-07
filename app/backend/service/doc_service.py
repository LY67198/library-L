"""文档管理业务逻辑 — Markdown 分块 + 嵌入 + ChromaDB 同步"""

from __future__ import annotations

import logging
import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.retrieval.chroma_retriever import ChromaDBRetriever
from agents.retrieval.embedder import QwenEmbedder
from models import DocSourceType, Document

logger = logging.getLogger(__name__)

# 默认 ChromaDB 数据目录
CHROMA_PERSIST_DIR = "./chroma_data"
COLLECTION_NAME = "library_policies"


def _chunk_markdown(text: str) -> list[str]:
    """按 ## 标题分节；超过 2000 字符的节按 1000 字符重叠切割"""
    sections = re.split(r"\n(?=## )", text)
    chunks: list[str] = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(section) <= 2000:
            chunks.append(section)
        else:
            # 重叠滑动窗口切割
            window = 1000
            overlap = 200
            start = 0
            while start < len(section):
                end = min(start + window, len(section))
                chunks.append(section[start:end])
                if end >= len(section):
                    break
                start = end - overlap
    return chunks


class DocService:

    def __init__(
        self,
        db: AsyncSession,
        retriever: ChromaDBRetriever | None = None,
        embedder: QwenEmbedder | None = None,
    ):
        self._db = db
        self._retriever = retriever or ChromaDBRetriever(
            collection_name=COLLECTION_NAME,
            persist_dir=CHROMA_PERSIST_DIR,
        )
        self._embedder = embedder or QwenEmbedder()

    async def list_docs(self) -> tuple[list[Document], int]:
        """列出所有文档"""
        result = await self._db.execute(select(Document).order_by(Document.created_at.desc()))
        docs = list(result.scalars().all())
        count_result = await self._db.execute(select(func.count(Document.id)))
        total = count_result.scalar() or 0
        return docs, total

    async def get_doc(self, doc_id: str) -> Document | None:
        result = await self._db.execute(select(Document).where(Document.id == doc_id))
        return result.scalar_one_or_none()

    async def upload(
        self, title: str, filename: str, source_type: str, content: str
    ) -> Document:
        """上传 Markdown 文件：分块 → 嵌入 → 写入 ChromaDB → 记录元数据"""
        # 1. 分块
        chunks_text = _chunk_markdown(content)
        if not chunks_text:
            raise ValueError("文档内容为空，无法分块")

        # 2. 嵌入
        try:
            embeddings = self._embedder.embed(chunks_text)
        except Exception as exc:
            raise RuntimeError(f"嵌入失败: {exc}")

        # 3. 创建 PG 记录（先获得 doc_id）
        doc = Document(
            title=title,
            filename=filename,
            source_type=DocSourceType(source_type),
            chunk_count=len(chunks_text),
        )
        self._db.add(doc)
        await self._db.commit()
        await self._db.refresh(doc)

        # 4. 写入 ChromaDB
        try:
            chunks_payload = []
            for i, (ct, emb) in enumerate(zip(chunks_text, embeddings)):
                chunks_payload.append({
                    "id": f"{doc.id}_{i}",
                    "document": ct,
                    "embedding": emb,
                    "metadata": {
                        "doc_id": doc.id,
                        "title": title,
                        "source_type": source_type,
                        "chunk_index": i,
                        "chunk_total": len(chunks_text),
                    },
                })
            self._retriever.add_documents(chunks_payload)
        except Exception as exc:
            # ChromaDB 写入失败则回滚 PG 记录
            await self._db.delete(doc)
            await self._db.commit()
            raise RuntimeError(f"ChromaDB 写入失败: {exc}")

        return doc

    async def delete(self, doc_id: str) -> bool:
        """删除文档：PG 记录 + ChromaDB chunks"""
        doc = await self.get_doc(doc_id)
        if doc is None:
            return False

        # 先删 ChromaDB（即使失败也不阻塞 PG 删除）
        try:
            self._retriever.delete_by_doc_id(doc_id)
        except Exception as exc:
            logger.warning(f"ChromaDB 删除失败 {doc_id}: {exc}")

        await self._db.delete(doc)
        await self._db.commit()
        return True
