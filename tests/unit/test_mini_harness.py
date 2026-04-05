from pathlib import Path

from recalllayer.benchmark.mini_harness import run_mini_harness
from recalllayer.engine.local_db import LocalVectorDatabase


def test_mini_harness_runs_on_local_db(tmp_path: Path) -> None:
    db = LocalVectorDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={})
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={})

    result = run_mini_harness(db, [[0.9, 0.1], [0.1, 0.9]], top_k=1)

    assert result.recall_at_1 == 1.0
    assert result.exact_elapsed_ms >= 0.0
    assert result.compressed_elapsed_ms >= 0.0
