from __future__ import annotations

from recalllayer.engine.inspected_db import InspectedShowcaseDatabase
from recalllayer.engine.showcase_scored_db import ShowcaseScoredDatabase


def test_scored_hits_materialize_non_default_shard_mutable_tail(tmp_path) -> None:
    db = ShowcaseScoredDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={}, shard_id="shard-0")
    db.flush_mutable(shard_id="shard-0", segment_id="seg-a", generation=1)
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={}, shard_id="shard-1")
    db.flush_mutable(shard_id="shard-1", segment_id="seg-b", generation=1)
    db.upsert(vector_id="tail-b", embedding=[0.1, 0.9], metadata={"region": "us"}, shard_id="shard-1")

    hits = db.query_exact_hybrid_hits([0.0, 1.0], top_k=3, shard_id="shard-1")

    ids = [hit.vector_id for hit in hits]
    assert ids[:2] == ["b", "tail-b"]
    assert any(hit.vector_id == "tail-b" and hit.metadata["region"] == "us" for hit in hits)


def test_reranked_hits_use_non_default_shard_mutable_exact_search(tmp_path) -> None:
    db = ShowcaseScoredDatabase(
        collection_id="documents",
        root_dir=tmp_path,
        enable_ivf=True,
        ivf_n_clusters=4,
        ivf_probe_k=1,
        rerank_probe_k=2,
        enable_segment_cache=False,
    )
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={}, shard_id="shard-0")
    db.flush_mutable(shard_id="shard-0", segment_id="seg-a", generation=1)
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={}, shard_id="shard-1")
    db.flush_mutable(shard_id="shard-1", segment_id="seg-b", generation=1)
    db.upsert(vector_id="tail-b", embedding=[0.02, 0.98], metadata={"kind": "tail"}, shard_id="shard-1")

    hits = db.query_compressed_reranked_hybrid_hits([0.0, 1.0], top_k=2, candidate_k=4, shard_id="shard-1")

    ids = [hit.vector_id for hit in hits]
    assert "tail-b" in ids
    assert all(hit.vector_id != "a" for hit in hits)


def test_inspected_query_paths_respect_requested_shard_mutable_rows(tmp_path) -> None:
    db = InspectedShowcaseDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "ca"}, shard_id="shard-0")
    db.flush_mutable(shard_id="shard-0", segment_id="seg-a", generation=1)
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={"region": "us"}, shard_id="shard-1")
    db.flush_mutable(shard_id="shard-1", segment_id="seg-b", generation=1)
    db.upsert(vector_id="tail-b", embedding=[0.05, 0.95], metadata={"region": "us"}, shard_id="shard-1")

    result = db.query_exact_hybrid_inspected([0.0, 1.0], top_k=3, shard_id="shard-1")

    ids = [hit.vector_id for hit in result.hits]
    assert ids[:2] == ["b", "tail-b"]
    assert result.inspection.mutable_live_count == 1
    assert result.inspection.sealed_segment_count == 1


def test_query_snapshot_returns_requested_shard_watermark(tmp_path) -> None:
    db = ShowcaseScoredDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={}, shard_id="shard-0")
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={}, shard_id="shard-1")
    db.flush_mutable(shard_id="shard-0", segment_id="seg-a", generation=1)

    _paths, watermark = db._query_snapshot(shard_id="shard-1")

    assert watermark == db._get_mutable_buffer("shard-1").watermark()
    assert watermark == 2
