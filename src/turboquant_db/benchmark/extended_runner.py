from __future__ import annotations

from dataclasses import dataclass

from turboquant_db.benchmark.comparison import ComparisonRow
from turboquant_db.benchmark.generated_fixtures import medium_synthetic_fixture
from turboquant_db.benchmark.mini_harness import run_mini_harness
from turboquant_db.engine.showcase_scored_db import ShowcaseScoredDatabase
from turboquant_db.quantization.experiments import NormalizedScalarQuantizer, ShiftedTurboQuantAdapter
from turboquant_db.quantization.scalar import ScalarQuantizer
from turboquant_db.quantization.turboquant_adapter import TurboQuantAdapter


@dataclass(slots=True)
class ExtendedRunArtifacts:
    rows: list[ComparisonRow]
    fixture_name: str
    query_count: int


def run_extended_benchmark(root_prefix: str = ".extended_benchmark") -> ExtendedRunArtifacts:
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
            root_dir=f"{root_prefix}-{index}",
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

    return ExtendedRunArtifacts(rows=rows, fixture_name=dataset.name, query_count=len(dataset.queries))
