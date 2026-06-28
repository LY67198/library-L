"""Sliding-window text chunker."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
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
    """Split text into overlapping chunks.

    Args:
        text: input string
        chunk_size: target chunk size in characters
        overlap: overlap between consecutive chunks
        min_chunk: drop trailing chunks shorter than this (unless it's the only chunk)
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
    import hashlib
    return hashlib.sha1(content.encode("utf-8")).hexdigest()