from app.rag.chunker import Chunk, chunk_text


def test_short_text_single_chunk():
    text = "hello world"
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0].content == "hello world"


def test_respects_max_chunk_size():
    text = "a" * 1500
    chunks = chunk_text(text, chunk_size=500, overlap=80)
    assert len(chunks) >= 3
    for c in chunks:
        assert len(c.content) <= 500


def test_overlap_between_consecutive_chunks():
    text = ("word " * 200).strip()  # 1000 chars
    chunks = chunk_text(text, chunk_size=200, overlap=50)
    assert len(chunks) >= 4
    # Last `overlap` chars of chunk[i] should appear at start of chunk[i+1]
    for a, b in zip(chunks, chunks[1:]):
        tail = a.content[-50:]
        head = b.content[:50]
        assert tail in head or head.startswith(tail[:25])


def test_chunks_have_offsets():
    text = "abcdefghij" * 100  # 1000 chars
    chunks = chunk_text(text, chunk_size=300, overlap=50)
    for c in chunks:
        assert isinstance(c.start_offset, int)
        assert isinstance(c.end_offset, int)
        assert 0 <= c.start_offset < c.end_offset <= len(text)


def test_empty_text_returns_empty_list():
    assert chunk_text("") == []