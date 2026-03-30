from pathlib import Path

from turboquant_db.engine.inspected_db import InspectedShowcaseDatabase
from turboquant_db.filters import FilterPlanner


def test_inspected_db_returns_real_counts_for_mixed_mutable_and_sealed_hits(tmp_path: Path) -> None:
    db = InspectedShowcaseDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="sealed-1", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.flush_mutable(segment_id="seg-1", generation=1)
    db.upsert(vector_id="mutable-1", embedding=[0.95, 0.05], metadata={"region": "us"})

    result = db.query_compressed_reranked_hybrid_inspected(
        [1.0, 0.0],
        top_k=2,
        filters={"region": {"eq": "us"}},
    )

    assert result.hits
    assert result.plan.mode == "compressed-reranked-hybrid"
    assert result.plan.candidate_k == 8
    assert result.inspection.pre_filter_candidate_count >= 2
    assert result.inspection.post_filter_candidate_count >= 2
    assert result.stats.pre_filter_candidate_count == result.inspection.pre_filter_candidate_count
    assert result.stats.post_filter_candidate_count == result.inspection.post_filter_candidate_count
    assert result.stats.mutable_hit_count == result.inspection.mutable_hit_count
    assert result.stats.sealed_hit_count == result.inspection.sealed_hit_count
    assert result.stats.mutable_hit_count + result.stats.sealed_hit_count == len(result.hits)
    assert result.inspection.total_latency_ms >= result.inspection.search_latency_ms


def test_inspected_db_exact_path_reports_zero_rerank_latency(tmp_path: Path) -> None:
    db = InspectedShowcaseDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us"})

    result = db.query_exact_hybrid_inspected([1.0, 0.0], top_k=1)

    assert result.hits[0].vector_id == "a"
    assert result.plan.mode == "exact-hybrid"
    assert result.stats.mutable_hit_count == 1
    assert result.stats.sealed_hit_count == 0
    assert result.inspection.rerank_candidate_k is None
    assert result.inspection.rerank_latency_ms == 0.0


def test_inspected_db_uses_candidate_restricted_helpers_for_selective_prefilter(tmp_path: Path) -> None:
    db = InspectedShowcaseDatabase(
        collection_id="documents",
        root_dir=tmp_path,
        filter_planner=FilterPlanner(prefilter_threshold=0.5),
    )
    db.upsert(vector_id="sealed-us", embedding=[0.95, 0.05], metadata={"region": "us"})
    db.upsert(vector_id="sealed-ca", embedding=[1.0, 0.0], metadata={"region": "ca"})
    db.upsert(vector_id="sealed-eu", embedding=[0.98, 0.02], metadata={"region": "eu"})
    db.flush_mutable(segment_id="seg-1", generation=1)
    db.upsert(vector_id="mutable-us", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.upsert(vector_id="mutable-ca", embedding=[0.99, 0.01], metadata={"region": "ca"})
    db.upsert(vector_id="mutable-eu", embedding=[0.97, 0.03], metadata={"region": "eu"})

    result = db.query_compressed_hybrid_inspected(
        [1.0, 0.0],
        top_k=3,
        filters={"region": {"eq": "us"}},
    )

    assert result.plan.filter_strategy == "pre-filter"
    assert [hit.vector_id for hit in result.hits] == ["mutable-us", "sealed-us"]
    assert result.inspection.pre_filter_candidate_count >= 6
    assert result.inspection.post_filter_candidate_count >= 2


def test_inspected_db_sealed_candidate_restriction_skips_rows_outside_candidate_set(tmp_path: Path) -> None:
    db = InspectedShowcaseDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="sealed-1", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.upsert(vector_id="sealed-2", embedding=[0.0, 1.0], metadata={"region": "ca"})
    db.flush_mutable(segment_id="seg-1", generation=1)

    exact = db._query_sealed_exactish([1.0, 0.0], top_k=5, candidate_ids={"sealed-2"})
    compressed = db._query_sealed_compressed([1.0, 0.0], top_k=5, candidate_ids={"sealed-2"})
    empty = db._query_sealed_exactish([1.0, 0.0], top_k=5, candidate_ids=set())

    assert [candidate.vector_id for candidate in exact] == ["sealed-2"]
    assert [candidate.vector_id for candidate in compressed] == ["sealed-2"]
    assert empty == []
