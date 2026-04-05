from pathlib import Path

from recalllayer.engine.showcase_scored_db import ShowcaseScoredDatabase


def test_showcase_scored_db_returns_scores_and_metadata(tmp_path: Path) -> None:
    db = ShowcaseScoredDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={"region": "ca"})
    db.flush_mutable(segment_id="seg-1", generation=1)

    hits = db.query_compressed_reranked_hybrid_hits([1.0, 0.0], top_k=2, filters={"region": {"eq": "us"}})

    assert hits
    assert hits[0].vector_id == "a"
    assert hits[0].metadata["region"] == "us"
    assert hits[0].score > 0.0
