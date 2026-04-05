from dataclasses import dataclass


@dataclass(slots=True)
class QueryPlan:
    mode: str
    approximate: bool
    rerank: bool
    top_k: int
    candidate_k: int | None
    filters_applied: bool
    filter_strategy: str


def build_query_plan(
    *,
    top_k: int,
    approximate: bool,
    rerank: bool,
    filters_applied: bool,
    filter_strategy: str = "post-filter",
    candidate_k: int | None = None,
) -> QueryPlan:
    normalized_candidate_k = None
    if rerank:
        normalized_candidate_k = max(candidate_k or (top_k * 4), top_k)

    if approximate and rerank:
        mode = "compressed-reranked-hybrid"
    elif approximate:
        mode = "compressed-hybrid"
    else:
        mode = "exact-hybrid"

    return QueryPlan(
        mode=mode,
        approximate=approximate,
        rerank=rerank,
        top_k=top_k,
        candidate_k=normalized_candidate_k,
        filters_applied=filters_applied,
        filter_strategy=filter_strategy,
    )
