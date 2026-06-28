"""文本分块测试 — 验证 chunk_text 的单块行为、最大长度限制、相邻块 overlap 与偏移量正确性。"""
from app.rag.chunker import Chunk, chunk_text


def test_short_text_single_chunk():
    """测试短文本:应被分成单个 Chunk,且 content 与原文完全一致。"""
    text = "hello world"
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0].content == "hello world"


def test_respects_max_chunk_size():
    """测试最大块大小约束:长文本按 chunk_size=500 切片后,每个 Chunk 的 content 不超过 500 字符。"""
    text = "a" * 1500
    chunks = chunk_text(text, chunk_size=500, overlap=80)
    assert len(chunks) >= 3
    for c in chunks:
        assert len(c.content) <= 500


def test_overlap_between_consecutive_chunks():
    """测试相邻块 overlap:后一块的开头应与前一块的尾部 overlap 字符保持一致,实现上下文连续。"""
    text = ("word " * 200).strip()  # 1000 chars
    chunks = chunk_text(text, chunk_size=200, overlap=50)
    assert len(chunks) >= 4
    # Last `overlap` chars of chunk[i] should appear at start of chunk[i+1]
    for a, b in zip(chunks, chunks[1:]):
        tail = a.content[-50:]
        head = b.content[:50]
        assert tail in head or head.startswith(tail[:25])


def test_chunks_have_offsets():
    """测试 Chunk 携带的 start_offset/end_offset 为合法整数,且落在原文区间内。"""
    text = "abcdefghij" * 100  # 1000 chars
    chunks = chunk_text(text, chunk_size=300, overlap=50)
    for c in chunks:
        assert isinstance(c.start_offset, int)
        assert isinstance(c.end_offset, int)
        assert 0 <= c.start_offset < c.end_offset <= len(text)


def test_empty_text_returns_empty_list():
    """测试空文本输入:应直接返回空列表,不产生任何 Chunk。"""
    assert chunk_text("") == []