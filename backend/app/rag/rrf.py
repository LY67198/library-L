"""Reciprocal Rank Fusion — pure function, no I/O."""
from __future__ import annotations

from collections import defaultdict

from app.rag.bm25_retriever import Hit


def reciprocal_rank_fusion(
    hit_lists: list[list[Hit]],
    *,
    k: int = 60,
) -> list[Hit]:
    """Fuse multiple ranked lists into one via RRF.

    score(d) = Σ 1 / (k + rank_i(d))

    For duplicate chunk_ids across lists, keeps the longest content version.
    """
    rrf_scores: dict[str, float] = defaultdict(float)
    hit_map: dict[str, Hit] = {}

    for hits in hit_lists:
        for rank, hit in enumerate(hits, start=1):
            rrf_scores[hit.chunk_id] += 1.0 / (k + rank)
            existing = hit_map.get(hit.chunk_id)
            if existing is None or len(hit.content) > len(existing.content):
                hit_map[hit.chunk_id] = hit

    sorted_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)
    return [
        Hit(
            chunk_id=cid,
            source_id=hit_map[cid].source_id,
            title=hit_map[cid].title,
            content=hit_map[cid].content,
            score=rrf_scores[cid],
            rank=i + 1,
        )
        for i, cid in enumerate(sorted_ids)
    ]
