from pathlib import Path

from recalllayer.benchmark.mini_harness import run_mini_harness
from recalllayer.engine.local_db import LocalVectorDatabase
from recalllayer.engine.showcase_scored_db import ShowcaseScoredDatabase


def test_mini_harness_runs_on_local_db(tmp_path: Path) -> None:
    db = LocalVectorDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={})
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={})

    result = run_mini_harness(db, [[0.9, 0.1], [0.1, 0.9]], top_k=1)

    assert result.recall_at_1 == 1.0
    assert result.exact_elapsed_ms >= 0.0
    assert result.compressed_elapsed_ms >= 0.0


def test_mini_harness_tracks_hybrid_trace_and_cache_stats(tmp_path: Path) -> None:
    db = ShowcaseScoredDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={"region": "ca"})
    db.flush_mutable(segment_id="seg-1", generation=1)

    result = run_mini_harness(db, [[1.0, 0.0], [1.0, 0.0]], top_k=1)

    assert result.exact.path_name == "exact-hybrid"
    assert result.compressed.path_name == "compressed-hybrid"
    assert result.reranked is not None
    assert result.compressed.trace["candidate_generation_count"] >= 1.0
    assert result.compressed.cache_stats["indexed_cache"]["hits"] >= 1
    assert result.reranked.trace["rerank_latency_ms"] >= 0.0
