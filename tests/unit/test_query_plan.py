from recalllayer.engine.query_plan import build_query_plan


def test_build_query_plan_normalizes_rerank_candidate_k() -> None:
    plan = build_query_plan(top_k=5, approximate=True, rerank=True, filters_applied=True, candidate_k=3)
    assert plan.mode == "compressed-reranked-hybrid"
    assert plan.candidate_k == 5
    assert plan.filter_strategy == "post-filter"


def test_build_query_plan_uses_exact_mode_without_rerank() -> None:
    plan = build_query_plan(top_k=3, approximate=False, rerank=False, filters_applied=False)
    assert plan.mode == "exact-hybrid"
    assert plan.candidate_k is None
    assert plan.filters_applied is False
