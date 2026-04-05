from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable

from recalllayer.benchmark.metrics import average_latency_ms, recall_at_k
from recalllayer.engine.local_db import LocalVectorDatabase


@dataclass(slots=True)
class HarnessPathResult:
    path_name: str
    latency_ms: float
    recall_at_1: float
    recall_at_10: float
    trace: dict[str, Any] = field(default_factory=dict)
    cache_stats: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class HarnessResult:
    exact: HarnessPathResult
    compressed: HarnessPathResult
    reranked: HarnessPathResult | None = None

    @property
    def exact_elapsed_ms(self) -> float:
        return self.exact.latency_ms

    @property
    def compressed_elapsed_ms(self) -> float:
        return self.compressed.latency_ms

    @property
    def recall_at_1(self) -> float:
        return self.compressed.recall_at_1

    @property
    def recall_at_10(self) -> float:
        return self.compressed.recall_at_10


def run_mini_harness(
    db: LocalVectorDatabase, queries: list[list[float]], *, top_k: int = 10
) -> HarnessResult:
    if hasattr(db, "query_exact_hybrid_hits") and hasattr(db, "query_compressed_hybrid_hits"):
        exact_ids, exact_trace, exact_cache, exact_latency_ms = _run_path(
            db,
            queries,
            query_fn=lambda query: db.query_exact_hybrid_hits(query, top_k=top_k),
        )
        compressed_ids, compressed_trace, compressed_cache, compressed_latency_ms = _run_path(
            db,
            queries,
            query_fn=lambda query: db.query_compressed_hybrid_hits(query, top_k=top_k),
        )
        reranked: HarnessPathResult | None = None
        if hasattr(db, "query_compressed_reranked_hybrid_hits"):
            reranked_ids, reranked_trace, reranked_cache, reranked_latency_ms = _run_path(
                db,
                queries,
                query_fn=lambda query: db.query_compressed_reranked_hybrid_hits(query, top_k=top_k),
            )
            reranked = HarnessPathResult(
                path_name="compressed-reranked-hybrid",
                latency_ms=reranked_latency_ms,
                recall_at_1=recall_at_k(expected_ids=exact_ids, actual_ids=reranked_ids, k=1),
                recall_at_10=recall_at_k(
                    expected_ids=exact_ids, actual_ids=reranked_ids, k=min(10, top_k)
                ),
                trace=reranked_trace,
                cache_stats=reranked_cache,
            )
        return HarnessResult(
            exact=HarnessPathResult(
                path_name="exact-hybrid",
                latency_ms=exact_latency_ms,
                recall_at_1=1.0,
                recall_at_10=1.0,
                trace=exact_trace,
                cache_stats=exact_cache,
            ),
            compressed=HarnessPathResult(
                path_name="compressed-hybrid",
                latency_ms=compressed_latency_ms,
                recall_at_1=recall_at_k(expected_ids=exact_ids, actual_ids=compressed_ids, k=1),
                recall_at_10=recall_at_k(
                    expected_ids=exact_ids, actual_ids=compressed_ids, k=min(10, top_k)
                ),
                trace=compressed_trace,
                cache_stats=compressed_cache,
            ),
            reranked=reranked,
        )

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
        exact=HarnessPathResult(
            path_name="exact",
            latency_ms=exact_elapsed_ms,
            recall_at_1=1.0,
            recall_at_10=1.0,
        ),
        compressed=HarnessPathResult(
            path_name="compressed",
            latency_ms=compressed_elapsed_ms,
            recall_at_1=recall_at_k(expected_ids=exact_ids, actual_ids=compressed_ids, k=1),
            recall_at_10=recall_at_k(
                expected_ids=exact_ids, actual_ids=compressed_ids, k=min(10, top_k)
            ),
        ),
    )


def _run_path(
    db: LocalVectorDatabase,
    queries: list[list[float]],
    *,
    query_fn: Callable[[list[float]], list[object]],
) -> tuple[list[str], dict[str, Any], dict[str, Any], float]:
    if hasattr(db, "clear_segment_caches"):
        db.clear_segment_caches()
    if hasattr(db, "reset_segment_cache_stats"):
        db.reset_segment_cache_stats()
    ids: list[str] = []
    samples_ms: list[float] = []
    trace_totals: dict[str, float] = {
        "candidate_generation_count": 0.0,
        "mutable_candidate_count": 0.0,
        "sealed_candidate_count": 0.0,
        "result_count": 0.0,
        "rerank_candidate_count": 0.0,
        "mutable_search_latency_ms": 0.0,
        "sealed_search_latency_ms": 0.0,
        "merge_latency_ms": 0.0,
        "rerank_latency_ms": 0.0,
        "materialization_latency_ms": 0.0,
    }
    trace_mode = ""
    for query in queries:
        start = perf_counter()
        hits = query_fn(query)
        samples_ms.append((perf_counter() - start) * 1000.0)
        ids.extend(hit.vector_id if hasattr(hit, "vector_id") else hit for hit in hits)
        if hasattr(db, "last_query_trace"):
            trace = db.last_query_trace()
            trace_mode = str(trace.get("mode", trace_mode))
            for key in trace_totals:
                trace_totals[key] += float(trace.get(key) or 0.0)
    divisor = max(1, len(queries))
    averaged_trace = {key: value / divisor for key, value in trace_totals.items()}
    averaged_trace["mode"] = trace_mode
    cache_stats = db.segment_cache_stats() if hasattr(db, "segment_cache_stats") else {}
    return ids, averaged_trace, cache_stats, average_latency_ms(samples_ms)
