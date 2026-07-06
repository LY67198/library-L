"""检索器插件 — Retriever Protocol + 多种实现"""

from .protocol import Retriever, StubRetriever
from .chroma_retriever import ChromaDBRetriever
from .sql_book_lookup import SQLBookLookup

__all__ = ["Retriever", "StubRetriever", "ChromaDBRetriever", "SQLBookLookup"]
