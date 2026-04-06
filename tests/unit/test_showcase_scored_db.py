from pathlib import Path

from recalllayer.engine.showcase_scored_db import ShowcaseScoredDatabase


def test_showcase_scored_db_returns_scores_and_metadata(tmp_path: Path) -> None:
    db = ShowcaseScoredDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={"region": "ca"})
    db.flush_mutable(segment_id="seg-1", generation=1)

    hits = db.query_compressed_reranked_hybrid_hits(
        [1.0, 0.0], top_k=2, filters={"region": {"eq": "us"}}
    )

    assert hits
    assert hits[0].vector_id == "a"
    assert hits[0].metadata["region"] == "us"
    assert hits[0].score > 0.0


def test_showcase_scored_db_repeated_hybrid_paths_hit_segment_cache(tmp_path: Path) -> None:
    db = ShowcaseScoredDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.upsert(vector_id="b", embedding=[0.8, 0.2], metadata={"region": "us"})
    db.flush_mutable(segment_id="seg-1", generation=1)

    db.clear_segment_caches()
    db.reset_segment_cache_stats()
    db.query_exact_hybrid_hits([1.0, 0.0], top_k=2, filters={"region": {"eq": "us"}})
    first_exact = db.segment_cache_stats()
    db.query_exact_hybrid_hits([1.0, 0.0], top_k=2, filters={"region": {"eq": "us"}})
    second_exact = db.segment_cache_stats()

    assert first_exact["segment_reads"]["decode_loads"] == 1
    assert second_exact["decoded_cache"]["hits"] >= 1
    assert second_exact["segment_reads"]["decode_loads"] == 1

    db.clear_segment_caches()
    db.reset_segment_cache_stats()
    db.query_compressed_hybrid_hits([1.0, 0.0], top_k=2, filters={"region": {"eq": "us"}})
    first_compressed = db.segment_cache_stats()
    db.query_compressed_hybrid_hits([1.0, 0.0], top_k=2, filters={"region": {"eq": "us"}})
    second_compressed = db.segment_cache_stats()

    assert first_compressed["segment_reads"]["decode_loads"] == 1
    assert second_compressed["indexed_cache"]["hits"] >= 1
    assert second_compressed["segment_reads"]["decode_loads"] == 1

    db.clear_segment_caches()
    db.reset_segment_cache_stats()
    db.query_compressed_reranked_hybrid_hits([1.0, 0.0], top_k=2, filters={"region": {"eq": "us"}})
    first_reranked = db.segment_cache_stats()
    db.query_compressed_reranked_hybrid_hits([1.0, 0.0], top_k=2, filters={"region": {"eq": "us"}})
    second_reranked = db.segment_cache_stats()

    assert first_reranked["segment_reads"]["decode_loads"] == 1
    assert second_reranked["indexed_cache"]["hits"] >= 1
    assert second_reranked["decoded_cache"]["hits"] >= 1
    assert second_reranked["segment_reads"]["decode_loads"] == 1


def test_showcase_scored_db_materializes_hits_from_requested_shard_mutable_buffer(tmp_path: Path) -> None:
    db = ShowcaseScoredDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="shared", embedding=[0.0, 1.0], metadata={"region": "default"})
    db.upsert(
        vector_id="shared",
        embedding=[1.0, 0.0],
        metadata={"region": "named"},
        shard_id="shard-analytics",
    )

    hits = db.query_exact_hybrid_hits([1.0, 0.0], top_k=1, shard_id="shard-analytics")

    assert [hit.vector_id for hit in hits] == ["shared"]
    assert hits[0].metadata["region"] == "named"
    assert hits[0].score == 1.0


def test_showcase_scored_db_rerank_uses_requested_shard_mutable_rows(tmp_path: Path) -> None:
    db = ShowcaseScoredDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="sealed", embedding=[1.0, 0.0], metadata={"region": "named"}, shard_id="shard-analytics")
    db.flush_mutable(shard_id="shard-analytics", segment_id="seg-1", generation=1)
    db.upsert(vector_id="mutable", embedding=[1.0, 0.0], metadata={"region": "named"}, shard_id="shard-analytics")
    db.upsert(vector_id="mutable", embedding=[0.0, 1.0], metadata={"region": "default"})

    hits = db.query_compressed_reranked_hybrid_hits([1.0, 0.0], top_k=2, shard_id="shard-analytics")

    assert [hit.vector_id for hit in hits] == ["sealed", "mutable"]
    assert all(hit.metadata["region"] == "named" for hit in hits)
