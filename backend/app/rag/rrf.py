"""倒数排名融合(RRF)— 纯函数,无 I/O。

算法说明:
    多路召回的融合采用 Reciprocal Rank Fusion(RRF,Cormack et al., 2009),
    对每个 chunk_id 在每路列表中的排名按公式累加得分:

        score(d) = Σ_i  1 / (k + rank_i(d))

    其中 `k` 为平滑常数,默认 60,用于降低高排名(hit 的倒数大)对总分的支配;
    最后按总得分降序输出融合后的统一排名。重复 chunk_id 的元数据保留内容
    最长的一份,以避免被截断的版本覆盖完整版本。
"""
from __future__ import annotations

from collections import defaultdict

from app.rag.bm25_retriever import Hit


def reciprocal_rank_fusion(
    hit_lists: list[list[Hit]],
    *,
    k: int = 60,
) -> list[Hit]:
    """将多个已排序的 Hit 列表融合为单一排序列表。

    算法:RRF(Reciprocal Rank Fusion),对每个 chunk_id 在所有列表中的
    排名按 `1 / (k + rank)` 累加得分,按总得分降序输出;同 chunk_id
    的多份 Hit 保留 `content` 最长的版本。

    参数:
        hit_lists: 多个已按相关度排序的 Hit 列表(每路列表各自从 rank=1 起)。
        k: RRF 平滑常数,默认 60(经典取值,见 Cormack et al., 2009)。

    返回值:
        list[Hit]: 融合后的 Hit 列表,`score` 为 RRF 总分,`rank` 为融合后新排名(从 1 起)。
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
