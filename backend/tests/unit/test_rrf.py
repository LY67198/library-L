from app.rag.bm25_retriever import Hit
from app.rag.rrf import reciprocal_rank_fusion


def _hit(cid: str, rank: int, score: float = 1.0) -> Hit:
    return Hit(chunk_id=cid, source_id="s", title="", content=f"content-{cid}", score=score, rank=rank)


def test_rrf_single_list_preserves_order():
    hits = [_hit("a", 1), _hit("b", 2), _hit("c", 3)]
    fused = reciprocal_rank_fusion([hits], k=60)
    assert [h.chunk_id for h in fused] == ["a", "b", "c"]


def test_rrf_appears_in_multiple_lists_boosted():
    bm25 = [_hit("a", 1), _hit("b", 2)]
    dense = [_hit("b", 1), _hit("c", 2)]
    fused = reciprocal_rank_fusion([bm25, dense], k=60)
    # 'b' appears in both → highest RRF score
    assert fused[0].chunk_id == "b"


def test_rrf_k_parameter_affects_scores():
    hits = [_hit("a", 1)]
    fused_low = reciprocal_rank_fusion([hits], k=10)
    fused_high = reciprocal_rank_fusion([hits], k=100)
    assert fused_low[0].score > fused_high[0].score


def test_rrf_empty_lists():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[]]) == []


def test_rrf_picks_longer_content_for_duplicates():
    """When the same chunk_id appears in multiple lists with different content,
    RRF should keep the longest version."""
    short = _hit("x", 1)
    long = Hit(chunk_id="x", source_id="s", title="", content="a" * 500, score=1.0, rank=1)
    fused = reciprocal_rank_fusion([[short], [long]], k=60)
    assert fused[0].content == "a" * 500
