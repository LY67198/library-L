"""滑动窗口文本切分器 — 将长文本切分为带重叠的 Chunk 列表。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    """文本切片 — 包含内容、起止偏移与稳定 ID。"""

    content: str
    start_offset: int
    end_offset: int
    chunk_id: str  # sha1 of content


def chunk_text(
    text: str,
    *,
    chunk_size: int = 500,
    overlap: int = 80,
    min_chunk: int = 100,
) -> list[Chunk]:
    """将文本切分为带重叠的片段。

    参数:
        text: 输入文本。
        chunk_size: 每片目标字符数。
        overlap: 相邻片段之间的重叠字符数。
        min_chunk: 短于此长度的尾部片段将被丢弃(若为唯一片段则保留)。

    返回值:
        list[Chunk]: 切分后的 Chunk 列表。

    抛出:
        ValueError: 当 `chunk_size <= overlap` 时。
    """
    text = text.strip()
    if not text:
        return []

    chunks: list[Chunk] = []
    step = chunk_size - overlap
    if step <= 0:
        raise ValueError("chunk_size must be > overlap")

    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        content = text[start:end]
        if len(content) >= min_chunk or not chunks:
            chunk_id = _hash(content)
            chunks.append(Chunk(content=content, start_offset=start, end_offset=end, chunk_id=chunk_id))
        if end == len(text):
            break
        start += step
    return chunks


def _hash(content: str) -> str:
    """计算内容 SHA1 摘要,作为 Chunk ID。

    参数:
        content: 待哈希的文本。

    返回值:
        str: 40 字符十六进制摘要。
    """
    import hashlib
    return hashlib.sha1(content.encode("utf-8")).hexdigest()