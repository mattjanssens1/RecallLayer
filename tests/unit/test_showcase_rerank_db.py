from pathlib import Path

from turboquant_db.engine.showcase_rerank_db import ShowcaseRerankDatabase


def test_showcase_rerank_hybrid_returns_ranked_ids(tmp_path: Path) -> None:
    db = ShowcaseRerankDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={"region": "ca"})
    db.flush_mutable(segment_id="seg-1", generation=1)
    db.upsert(vector_id="c", embedding=[0.95, 0.05], metadata={"region": "us"})

    result = db.query_compressed_reranked_hybrid([1.0, 0.0], top_k=2, filters={"region": {"eq": "us"}})

    assert result
    assert result[0] in {"a", "c"}
