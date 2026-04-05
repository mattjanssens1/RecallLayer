from __future__ import annotations

from pathlib import Path

from recalllayer.benchmark.comparison import ComparisonRow, render_markdown_table
from recalllayer.benchmark.fixture_loader import load_fixture
from recalllayer.benchmark.mini_harness import run_mini_harness
from recalllayer.engine.showcase_scored_db import ShowcaseScoredDatabase


def main() -> None:
    fixture = load_fixture(Path("benchmarks") / "fixtures" / "tiny_semantic.json")
    db = ShowcaseScoredDatabase(collection_id=fixture.name, root_dir=".fixture_benchmark_db")

    for item in fixture.items:
        db.upsert(vector_id=item.vector_id, embedding=item.embedding, metadata=item.metadata)
    db.flush_mutable(segment_id="seg-1", generation=1)

    result = run_mini_harness(db, fixture.queries, top_k=2)
    table = render_markdown_table(
        [
            ComparisonRow(
                name=fixture.name,
                latency_ms=result.compressed_elapsed_ms,
                recall_at_1=result.recall_at_1,
                recall_at_10=result.recall_at_10,
            )
        ]
    )

    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / f"{fixture.name}_comparison.md"
    output_path.write_text(table + "\n", encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
