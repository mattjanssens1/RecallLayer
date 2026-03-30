from dataclasses import dataclass


@dataclass(slots=True)
class QueryStats:
    pre_filter_candidate_count: int
    post_filter_candidate_count: int
    mutable_hit_count: int
    sealed_hit_count: int


def build_query_stats(
    *,
    result_ids: list[str],
    source_by_vector_id: dict[str, str],
    pre_filter_candidate_count: int,
    post_filter_candidate_count: int,
) -> QueryStats:
    mutable_hit_count = sum(1 for vector_id in result_ids if source_by_vector_id.get(vector_id) == "mutable")
    sealed_hit_count = sum(1 for vector_id in result_ids if source_by_vector_id.get(vector_id) == "sealed")
    return QueryStats(
        pre_filter_candidate_count=pre_filter_candidate_count,
        post_filter_candidate_count=post_filter_candidate_count,
        mutable_hit_count=mutable_hit_count,
        sealed_hit_count=sealed_hit_count,
    )
