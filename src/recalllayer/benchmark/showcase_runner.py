from __future__ import annotations

from dataclasses import dataclass

from recalllayer.benchmark.comparison import ComparisonRow
from recalllayer.benchmark.fixtures import tiny_fixture
from recalllayer.benchmark.mini_harness import run_mini_harness
from recalllayer.engine.showcase_scored_db import ShowcaseScoredDatabase


@dataclass(slots=True)
class ShowcaseRunArtifacts:
    rows: list[ComparisonRow]


def run_showcase_benchmark(root_dir: str = ".showcase_benchmark_db") -> ShowcaseRunArtifacts:
    dataset = tiny_fixture()
    db = ShowcaseScoredDatabase(collection_id=dataset.name, root_dir=root_dir)
    for item in dataset.items:
        db.upsert(vector_id=item.vector_id, embedding=item.embedding, metadata=item.metadata)
    db.flush_mutable(segment_id="seg-1", generation=1)

    result = run_mini_harness(db, dataset.queries, top_k=2)
    rows = [
        ComparisonRow(
            name=f"showcase-scored-db:{result.exact.path_name}",
            latency_ms=result.exact.latency_ms,
            recall_at_1=result.exact.recall_at_1,
            recall_at_10=result.exact.recall_at_10,
        ),
        ComparisonRow(
            name=f"showcase-scored-db:{result.compressed.path_name}",
            latency_ms=result.compressed.latency_ms,
            recall_at_1=result.compressed.recall_at_1,
            recall_at_10=result.compressed.recall_at_10,
        ),
    ]
    if result.reranked is not None:
        rows.append(
            ComparisonRow(
                name=f"showcase-scored-db:{result.reranked.path_name}",
                latency_ms=result.reranked.latency_ms,
                recall_at_1=result.reranked.recall_at_1,
                recall_at_10=result.reranked.recall_at_10,
            )
        )
    return ShowcaseRunArtifacts(rows=rows)
