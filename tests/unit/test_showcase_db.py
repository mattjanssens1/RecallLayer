from pathlib import Path

from turboquant_db.engine.showcase_db import ShowcaseLocalDatabase


def test_showcase_db_hybrid_query_and_filter(tmp_path: Path) -> None:
    db = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={"region": "ca"})
    db.flush_mutable(segment_id="seg-1", generation=1)
    db.upsert(vector_id="c", embedding=[0.9, 0.1], metadata={"region": "us"})

    assert db.query_exact_hybrid([1.0, 0.0], top_k=2)[0] in {"a", "c"}
    assert db.query_compressed_hybrid([1.0, 0.0], top_k=2, filters={"region": {"eq": "us"}})
