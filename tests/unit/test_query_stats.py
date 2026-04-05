from recalllayer.engine.query_stats import build_query_stats


def test_build_query_stats_counts_mutable_and_sealed_hits() -> None:
    stats = build_query_stats(
        result_ids=["a", "b", "c"],
        source_by_vector_id={"a": "mutable", "b": "sealed", "c": "mutable"},
        pre_filter_candidate_count=9,
        post_filter_candidate_count=4,
    )

    assert stats.pre_filter_candidate_count == 9
    assert stats.post_filter_candidate_count == 4
    assert stats.mutable_hit_count == 2
    assert stats.sealed_hit_count == 1
