from __future__ import annotations

from pathlib import Path

from turboquant_db.benchmark.comparison import ComparisonRow, render_markdown_table
from turboquant_db.benchmark.mini_harness import run_mini_harness
from turboquant_db.engine.showcase_rerank_db import ShowcaseRerankDatabase


def main() -> None:
    db = ShowcaseRerankDatabase(collection_id="markdown-demo", root_dir=".markdown_demo_db")
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={"region": "ca"})
    db.upsert(vector_id="c", embedding=[0.8, 0.2], metadata={"region": "us"})
    db.flush_mutable(segment_id="seg-1", generation=1)

    result = run_mini_harness(db, [[0.9, 0.1], [0.1, 0.9]], top_k=2)
    table = render_markdown_table(
        [
            ComparisonRow(
                name="showcase-rerank-db",
                latency_ms=result.compressed_elapsed_ms,
                recall_at_1=result.recall_at_1,
                recall_at_10=result.recall_at_10,
            )
        ]
    )
    output_path = Path("reports") / "mini_benchmark_comparison.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(table + "\n", encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
