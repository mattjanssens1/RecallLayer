from __future__ import annotations

from dataclasses import dataclass

from recalllayer.benchmark.cluster_fixtures import clustered_fixture
from recalllayer.benchmark.fixtures import tiny_fixture
from recalllayer.benchmark.mini_harness import HarnessPathResult, run_mini_harness
from recalllayer.engine.showcase_scored_db import ShowcaseScoredDatabase
from recalllayer.quantization.experiments import NormalizedScalarQuantizer
from recalllayer.quantization.scalar import ScalarQuantizer


@dataclass(slots=True)
class CacheSprint4Row:
    fixture_name: str
    quantizer_name: str
    cache_mode: str
    query_path: str
    latency_ms: float
    cache_hit_rate: float
    file_reads: int
    decode_loads: int
    candidate_generation_count: float
    rerank_latency_ms: float


def build_cache_sprint4_rows(root_prefix: str = ".cache_sprint4") -> list[CacheSprint4Row]:
    rows: list[CacheSprint4Row] = []
    fixtures = [
        (tiny_fixture(), 2),
        (clustered_fixture(size_per_cluster=16), 5),
    ]
    quantizers = [
        ScalarQuantizer(),
        NormalizedScalarQuantizer(),
    ]
    for fixture_index, (dataset, top_k) in enumerate(fixtures):
        for quantizer_index, quantizer in enumerate(quantizers):
            for cache_enabled, cache_mode in ((False, "cache-disabled"), (True, "cache-enabled")):
                db = ShowcaseScoredDatabase(
                    collection_id=f"{dataset.name}-{quantizer.name}-{cache_mode}",
                    root_dir=f"{root_prefix}-{fixture_index}-{quantizer_index}-{cache_mode}",
                    quantizer=quantizer,
                    enable_segment_cache=cache_enabled,
                )
                for item in dataset.items:
                    db.upsert(
                        vector_id=item.vector_id, embedding=item.embedding, metadata=item.metadata
                    )
                db.flush_mutable(segment_id="seg-1", generation=1)
                result = run_mini_harness(db, dataset.queries, top_k=top_k)
                rows.extend(
                    _rows_for_result(
                        fixture_name=dataset.name,
                        quantizer_name=quantizer.name,
                        cache_mode=cache_mode,
                        result=result,
                    )
                )
    return rows


def render_cache_sprint4_markdown(rows: list[CacheSprint4Row]) -> str:
    lines = [
        "# Cache Sprint 4 Benchmark",
        "",
        (
            "| Fixture | Quantizer | Cache mode | Query path | Latency ms | Cache hit rate | "
            "File reads | Decode loads | Candidates | Rerank ms |"
        ),
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.fixture_name} | {row.quantizer_name} | {row.cache_mode} | "
            f"{row.query_path} | {row.latency_ms:.3f} | {row.cache_hit_rate:.3f} | "
            f"{row.file_reads} | {row.decode_loads} | "
            f"{row.candidate_generation_count:.1f} | {row.rerank_latency_ms:.3f} |"
        )
    return "\n".join(lines)


def summarize_cache_sprint4(rows: list[CacheSprint4Row]) -> str:
    indexed = {
        (row.fixture_name, row.quantizer_name, row.query_path, row.cache_mode): row for row in rows
    }
    lines = [
        "# Sprint 4 Cache Summary",
        "",
        (
            "Representative subset: `tiny_fixture` and `clustered_fixture`, using the "
            "canonical scalar quantizer plus `normalized-scalar` as a scalar control. "
            "`TurboQuantAdapter` is intentionally excluded from the canonical table "
            "and remains experimental only."
        ),
        "",
    ]
    for fixture_name, quantizer_name in sorted(
        {(row.fixture_name, row.quantizer_name) for row in rows}
    ):
        lines.append(f"## {fixture_name} / {quantizer_name}")
        for query_path in ("exact-hybrid", "compressed-hybrid", "compressed-reranked-hybrid"):
            before = indexed.get((fixture_name, quantizer_name, query_path, "cache-disabled"))
            after = indexed.get((fixture_name, quantizer_name, query_path, "cache-enabled"))
            if before is None or after is None:
                continue
            delta_ms = after.latency_ms - before.latency_ms
            lines.append(
                f"- `{query_path}`: {before.latency_ms:.3f} ms -> {after.latency_ms:.3f} ms "
                f"({delta_ms:+.3f} ms), cache hit rate {after.cache_hit_rate:.3f}, "
                f"file reads {before.file_reads} -> {after.file_reads}, decode loads "
                f"{before.decode_loads} -> {after.decode_loads}."
            )
        exact = indexed.get((fixture_name, quantizer_name, "exact-hybrid", "cache-enabled"))
        reranked = indexed.get(
            (fixture_name, quantizer_name, "compressed-reranked-hybrid", "cache-enabled")
        )
        compressed = indexed.get(
            (fixture_name, quantizer_name, "compressed-hybrid", "cache-enabled")
        )
        if exact is not None and compressed is not None and reranked is not None:
            lines.append(
                f"- With cache enabled, `compressed-reranked-hybrid` vs `exact-hybrid`: "
                f"{reranked.latency_ms:.3f} ms vs {exact.latency_ms:.3f} ms. "
                f"`compressed-hybrid` stays at {compressed.latency_ms:.3f} ms."
            )
        lines.append("")
    lines.extend(
        [
            "## Status",
            (
                "- Scalar quantizers (`scalar-quantizer`, `normalized-scalar`) remain "
                "the only canonical benchmarked quantizers in this report."
            ),
            (
                "- `TurboQuantAdapter` is not geometrically fixed in this sprint. "
                "The code stays in the repo for experiments, but canonical scripts "
                "and summary tables exclude it."
            ),
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _rows_for_result(
    *,
    fixture_name: str,
    quantizer_name: str,
    cache_mode: str,
    result: object,
) -> list[CacheSprint4Row]:
    rows = [
        _row(fixture_name, quantizer_name, cache_mode, result.exact),
        _row(fixture_name, quantizer_name, cache_mode, result.compressed),
    ]
    if result.reranked is not None:
        rows.append(_row(fixture_name, quantizer_name, cache_mode, result.reranked))
    return rows


def _row(
    fixture_name: str,
    quantizer_name: str,
    cache_mode: str,
    result: HarnessPathResult,
) -> CacheSprint4Row:
    indexed_cache = result.cache_stats.get("indexed_cache", {})
    decoded_cache = result.cache_stats.get("decoded_cache", {})
    reads = result.cache_stats.get("segment_reads", {})
    total_hits = float(indexed_cache.get("hits", 0)) + float(decoded_cache.get("hits", 0))
    total_misses = float(indexed_cache.get("misses", 0)) + float(decoded_cache.get("misses", 0))
    denominator = total_hits + total_misses
    return CacheSprint4Row(
        fixture_name=fixture_name,
        quantizer_name=quantizer_name,
        cache_mode=cache_mode,
        query_path=result.path_name,
        latency_ms=result.latency_ms,
        cache_hit_rate=(total_hits / denominator) if denominator else 0.0,
        file_reads=int(reads.get("file_reads", 0)),
        decode_loads=int(reads.get("decode_loads", 0)),
        candidate_generation_count=float(result.trace.get("candidate_generation_count", 0.0)),
        rerank_latency_ms=float(result.trace.get("rerank_latency_ms", 0.0)),
    )
