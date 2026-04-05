from __future__ import annotations

from pathlib import Path

from recalllayer.benchmark.mini_harness import run_mini_harness
from recalllayer.benchmark.report import BenchmarkSummary, write_summary
from recalllayer.engine.showcase_rerank_db import ShowcaseRerankDatabase


def main() -> None:
    db = ShowcaseRerankDatabase(collection_id="report-demo", root_dir=".report_demo_db")
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={"region": "ca"})
    db.upsert(vector_id="c", embedding=[0.8, 0.2], metadata={"region": "us"})
    db.flush_mutable(segment_id="seg-1", generation=1)

    result = run_mini_harness(db, [[0.9, 0.1], [0.1, 0.9]], top_k=2)
    summary = BenchmarkSummary(
        backend="showcase-rerank-db",
        query_count=2,
        elapsed_ms=result.compressed_elapsed_ms,
        recall_at_10=result.recall_at_10,
    )
    path = write_summary(summary, Path("reports") / "mini_benchmark_summary.json")
    print(path)


if __name__ == "__main__":
    main()
