"""RRF(倒数排名融合)测试 — 验证单列表保序、多列表加分、k 参数、边界与去重策略。"""
from __future__ import annotations

from app.rag.bm25_retriever import Hit
from app.rag.rrf import reciprocal_rank_fusion


def _hit(cid: str, rank: int, score: float = 1.0) -> Hit:
    return Hit(chunk_id=cid, source_id="s", title="", content=f"content-{cid}", score=score, rank=rank)


def test_rrf_single_list_preserves_order():
    """测试单列表融合:仅有一个排序列表时,RRF 输出顺序应与原列表一致。"""
    hits = [_hit("a", 1), _hit("b", 2), _hit("c", 3)]
    fused = reciprocal_rank_fusion([hits], k=60)
    assert [h.chunk_id for h in fused] == ["a", "b", "c"]


def test_rrf_appears_in_multiple_lists_boosted():
    """测试多列表融合:同一 chunk 在多个列表出现时应获得加分,最终排名靠前。"""
    bm25 = [_hit("a", 1), _hit("b", 2)]
    dense = [_hit("b", 1), _hit("c", 2)]
    fused = reciprocal_rank_fusion([bm25, dense], k=60)
    # 'b' appears in both → highest RRF score
    assert fused[0].chunk_id == "b"


def test_rrf_k_parameter_affects_scores():
    """测试 k 参数影响:k 越小,分数对排名越敏感,低 k 列表的相同 rank 分数应大于高 k 列表。"""
    hits = [_hit("a", 1)]
    fused_low = reciprocal_rank_fusion([hits], k=10)
    fused_high = reciprocal_rank_fusion([hits], k=100)
    assert fused_low[0].score > fused_high[0].score


def test_rrf_empty_lists():
    """测试空输入边界:无列表或仅含空列表时,RRF 应返回空列表,不抛异常。"""
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[]]) == []


def test_rrf_picks_longer_content_for_duplicates():
    """测试去重时保留长内容:同一 chunk_id 在多列表出现且 content 不同时,应保留更长的 content 版本。"""
    short = _hit("x", 1)
    long = Hit(chunk_id="x", source_id="s", title="", content="a" * 500, score=1.0, rank=1)
    fused = reciprocal_rank_fusion([[short], [long]], k=60)
    assert fused[0].content == "a" * 500
