"""ChromaDBRetriever 写入/删除/搜索联动测试"""
import pytest
from agents.retrieval.chroma_retriever import ChromaDBRetriever


@pytest.fixture
def retriever():
    r = ChromaDBRetriever(
        collection_name="test_policies",
        persist_dir="./chroma_test_data",
    )
    yield r
    # 清空测试 collection
    try:
        r._ensure_initialized()
        r._client.delete_collection("test_policies")
    except Exception:
        pass


def test_add_and_search(retriever):
    chunks = [
        {
            "id": "test-doc-1_0",
            "document": "图书馆每天早上8点开门，晚上10点关门。",
            "metadata": {"doc_id": "test-doc-1", "title": "开馆时间", "source_type": "policy", "chunk_index": 0, "chunk_total": 1},
        },
        {
            "id": "test-doc-2_0",
            "document": "每本书最多借阅30天，可续借一次。",
            "metadata": {"doc_id": "test-doc-2", "title": "借阅规则", "source_type": "rule", "chunk_index": 0, "chunk_total": 1},
        },
    ]
    retriever.add_documents(chunks)

    results = retriever.search("开馆时间", top_k=3)
    assert len(results) > 0
    assert any("8点" in r["content"] for r in results)


def test_delete_by_doc_id(retriever):
    chunks = [
        {
            "id": "del-test_0",
            "document": "将被删除的文档内容。",
            "metadata": {"doc_id": "del-test", "title": "测试", "source_type": "faq", "chunk_index": 0, "chunk_total": 1},
        },
    ]
    retriever.add_documents(chunks)

    # 确认存在
    results = retriever.search("删除的文档", top_k=3)
    assert any("删除" in r["content"] for r in results)

    # 删除
    retriever.delete_by_doc_id("del-test")

    # 确认不存在
    results = retriever.search("删除的文档", top_k=3)
    assert not any("删除" in r["content"] for r in results)


def test_add_empty_list(retriever):
    retriever.add_documents([])
    # 不应抛异常


def test_delete_nonexistent(retriever):
    retriever.delete_by_doc_id("nonexistent-doc-id")
    # 不应抛异常
