from __future__ import annotations

from pathlib import Path

from recalllayer.benchmark.comparison import ComparisonRow, render_markdown_table
from recalllayer.benchmark.generated_fixtures import medium_synthetic_fixture
from recalllayer.benchmark.mini_harness import run_mini_harness
from recalllayer.engine.showcase_scored_db import ShowcaseScoredDatabase
from recalllayer.quantization.experiments import NormalizedScalarQuantizer, ShiftedTurboQuantAdapter
from recalllayer.quantization.scalar import ScalarQuantizer
from recalllayer.quantization.turboquant_adapter import TurboQuantAdapter


def main() -> None:
    dataset = medium_synthetic_fixture()
    quantizers = [
        ScalarQuantizer(),
        NormalizedScalarQuantizer(),
        TurboQuantAdapter(),
        ShiftedTurboQuantAdapter(),
    ]

    rows: list[ComparisonRow] = []
    for index, quantizer in enumerate(quantizers):
        db = ShowcaseScoredDatabase(
            collection_id=f"{dataset.name}-{index}",
            root_dir=f".extended_benchmark_{index}",
            quantizer=quantizer,
        )
        for item in dataset.items:
            db.upsert(vector_id=item.vector_id, embedding=item.embedding, metadata=item.metadata)
        db.flush_mutable(segment_id="seg-1", generation=1)

        result = run_mini_harness(db, dataset.queries, top_k=5)
        rows.append(
            ComparisonRow(
                name=quantizer.name,
                latency_ms=result.compressed_elapsed_ms,
                recall_at_1=result.recall_at_1,
                recall_at_10=result.recall_at_10,
            )
        )

    output_path = Path("reports") / "extended_benchmark.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_table(rows) + "\n", encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
