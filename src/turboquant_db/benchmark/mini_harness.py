from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from turboquant_db.benchmark.metrics import recall_at_k
from turboquant_db.engine.local_db import LocalVectorDatabase


@dataclass(slots=True)
class HarnessResult:
    exact_elapsed_ms: float
    compressed_elapsed_ms: float
    recall_at_1: float
    recall_at_10: float


def run_mini_harness(db: LocalVectorDatabase, queries: list[list[float]], *, top_k: int = 10) -> HarnessResult:
    exact_ids: list[str] = []
    compressed_ids: list[str] = []

    start = perf_counter()
    for query in queries:
        exact_ids.extend(db.query_exact(query, top_k=top_k))
    exact_elapsed_ms = (perf_counter() - start) * 1000.0

    start = perf_counter()
    for query in queries:
        compressed_ids.extend(db.query_compressed(query, top_k=top_k))
    compressed_elapsed_ms = (perf_counter() - start) * 1000.0

    return HarnessResult(
        exact_elapsed_ms=exact_elapsed_ms,
        compressed_elapsed_ms=compressed_elapsed_ms,
        recall_at_1=recall_at_k(expected_ids=exact_ids, actual_ids=compressed_ids, k=1),
        recall_at_10=recall_at_k(expected_ids=exact_ids, actual_ids=compressed_ids, k=min(10, top_k)),
    )
