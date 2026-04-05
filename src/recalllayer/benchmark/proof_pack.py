from __future__ import annotations

from dataclasses import dataclass

from recalllayer.benchmark.cluster_fixtures import clustered_fixture
from recalllayer.benchmark.fixtures import tiny_fixture
from recalllayer.benchmark.mini_harness import HarnessPathResult, run_mini_harness
from recalllayer.engine.showcase_scored_db import ShowcaseScoredDatabase
from recalllayer.quantization.scalar import ScalarQuantizer


@dataclass(slots=True)
class ProofRow:
    fixture_name: str
    query_path: str
    backend: str
    latency_ms: float
    recall_at_1: float
    recall_at_10: float
    cache_hit_rate: float
    file_reads: int
    decode_loads: int
    candidate_generation_count: float
    rerank_latency_ms: float
    note: str


def render_proof_markdown(rows: list[ProofRow]) -> str:
    lines = [
        (
            "| Fixture | Query path | Backend | Latency ms | Recall@1 | Recall@10 | "
            "Cache hit rate | File reads | Decode loads | Candidates | Rerank ms | Note |"
        ),
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.fixture_name} | {row.query_path} | {row.backend} | "
            f"{row.latency_ms:.3f} | {row.recall_at_1:.3f} | {row.recall_at_10:.3f} | "
            f"{row.cache_hit_rate:.3f} | {row.file_reads} | {row.decode_loads} | "
            f"{row.candidate_generation_count:.1f} | {row.rerank_latency_ms:.3f} | "
            f"{row.note} |"
        )
    return "\n".join(lines)


def build_proof_rows(root_prefix: str = ".proof_pack") -> list[ProofRow]:
    fixture_specs = [
        (tiny_fixture(), 2),
        (clustered_fixture(size_per_cluster=16), 5),
    ]

    rows: list[ProofRow] = []
    for fixture_index, (dataset, top_k) in enumerate(fixture_specs):
        db = ShowcaseScoredDatabase(
            collection_id=f"{dataset.name}-scalar-{fixture_index}",
            root_dir=f"{root_prefix}-{fixture_index}",
            quantizer=ScalarQuantizer(),
        )
        for item in dataset.items:
            db.upsert(vector_id=item.vector_id, embedding=item.embedding, metadata=item.metadata)
        db.flush_mutable(segment_id="seg-1", generation=1)

        result = run_mini_harness(db, dataset.queries, top_k=top_k)
        rows.append(
            _row_from_result(
                dataset.name, "scalar-quantizer", result.exact, "Reference exact hybrid path."
            )
        )
        rows.append(
            _row_from_result(
                dataset.name,
                "scalar-quantizer",
                result.compressed,
                "Canonical compressed hybrid path.",
            )
        )
        if result.reranked is not None:
            rows.append(
                _row_from_result(
                    dataset.name,
                    "scalar-quantizer",
                    result.reranked,
                    "Canonical compressed+rereank path over cached sealed payloads.",
                )
            )

    return rows


def _row_from_result(
    fixture_name: str, backend: str, result: HarnessPathResult, note: str
) -> ProofRow:
    indexed_cache = result.cache_stats.get("indexed_cache", {})
    decoded_cache = result.cache_stats.get("decoded_cache", {})
    reads = result.cache_stats.get("segment_reads", {})
    total_hits = float(indexed_cache.get("hits", 0)) + float(decoded_cache.get("hits", 0))
    total_misses = float(indexed_cache.get("misses", 0)) + float(decoded_cache.get("misses", 0))
    denominator = total_hits + total_misses
    return ProofRow(
        fixture_name=fixture_name,
        query_path=result.path_name,
        backend=backend,
        latency_ms=result.latency_ms,
        recall_at_1=result.recall_at_1,
        recall_at_10=result.recall_at_10,
        cache_hit_rate=(total_hits / denominator) if denominator else 0.0,
        file_reads=int(reads.get("file_reads", 0)),
        decode_loads=int(reads.get("decode_loads", 0)),
        candidate_generation_count=float(result.trace.get("candidate_generation_count", 0.0)),
        rerank_latency_ms=float(result.trace.get("rerank_latency_ms", 0.0)),
        note=note,
    )
