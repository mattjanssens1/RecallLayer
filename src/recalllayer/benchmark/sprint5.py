"""Sprint 5 benchmark: compressed vs exact at scale with per-phase latency and IVF."""
from __future__ import annotations

from dataclasses import dataclass

from recalllayer.benchmark.medium_fixtures import medium_fixture
from recalllayer.benchmark.mini_harness import HarnessPathResult, run_mini_harness
from recalllayer.engine.showcase_scored_db import ShowcaseScoredDatabase
from recalllayer.quantization.scalar import ScalarQuantizer


@dataclass(slots=True)
class Sprint5Row:
    fixture_name: str
    quantizer_name: str
    ivf_mode: str
    query_path: str
    latency_ms: float
    mutable_search_ms: float
    sealed_search_ms: float
    rerank_ms: float
    recall_at_10: float
    candidate_count: float


def build_sprint5_rows(root_prefix: str = ".cache_sprint5") -> list[Sprint5Row]:
    dataset = medium_fixture()
    top_k = 10
    quantizer = ScalarQuantizer()
    rows: list[Sprint5Row] = []

    for enable_ivf, ivf_mode in ((False, "ivf-disabled"), (True, "ivf-enabled")):
        db = ShowcaseScoredDatabase(
            collection_id=f"{dataset.name}-{quantizer.name}-{ivf_mode}",
            root_dir=f"{root_prefix}-{ivf_mode}",
            quantizer=quantizer,
            enable_segment_cache=True,
            enable_ivf=enable_ivf,
            ivf_n_clusters=16,
            ivf_probe_k=3,
        )
        for item in dataset.items:
            db.upsert(vector_id=item.vector_id, embedding=item.embedding, metadata=item.metadata)
        db.flush_mutable(segment_id="seg-1", generation=1)

        result = run_mini_harness(db, dataset.queries, top_k=top_k)
        rows.extend(
            _rows_for_result(
                fixture_name=dataset.name,
                quantizer_name=quantizer.name,
                ivf_mode=ivf_mode,
                result=result,
            )
        )

    return rows


def render_sprint5_markdown(rows: list[Sprint5Row]) -> str:
    lines = [
        "# Sprint 5 Benchmark — Compressed vs Exact at Scale",
        "",
        "Fixture: `medium_fixture_5000x128` (5 000 vectors, 128-dim, cache enabled).",
        "",
        (
            "| Fixture | Quantizer | IVF | Query path | Latency ms | "
            "Mutable ms | Sealed ms | Rerank ms | Recall@10 | Candidates |"
        ),
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.fixture_name} | {row.quantizer_name} | {row.ivf_mode} | "
            f"{row.query_path} | {row.latency_ms:.3f} | "
            f"{row.mutable_search_ms:.3f} | {row.sealed_search_ms:.3f} | "
            f"{row.rerank_ms:.3f} | {row.recall_at_10:.3f} | {row.candidate_count:.1f} |"
        )
    return "\n".join(lines)


def summarize_sprint5(rows: list[Sprint5Row]) -> str:
    indexed = {
        (row.ivf_mode, row.query_path): row for row in rows
    }
    lines = ["# Sprint 5 Summary", ""]

    for ivf_mode in ("ivf-disabled", "ivf-enabled"):
        lines.append(f"## {ivf_mode}")
        exact = indexed.get((ivf_mode, "exact-hybrid"))
        compressed = indexed.get((ivf_mode, "compressed-hybrid"))
        reranked = indexed.get((ivf_mode, "compressed-reranked-hybrid"))
        if exact and compressed:
            delta = compressed.latency_ms - exact.latency_ms
            sign = "faster" if delta < 0 else "slower"
            lines.append(
                f"- `compressed-hybrid` vs `exact-hybrid`: "
                f"{compressed.latency_ms:.3f} ms vs {exact.latency_ms:.3f} ms "
                f"({abs(delta):.3f} ms {sign}), recall@10={compressed.recall_at_10:.3f}"
            )
        if exact and reranked:
            delta = reranked.latency_ms - exact.latency_ms
            sign = "faster" if delta < 0 else "slower"
            lines.append(
                f"- `compressed-reranked-hybrid` vs `exact-hybrid`: "
                f"{reranked.latency_ms:.3f} ms vs {exact.latency_ms:.3f} ms "
                f"({abs(delta):.3f} ms {sign}), recall@10={reranked.recall_at_10:.3f}"
            )
        if compressed:
            lines.append(
                f"- Phase breakdown (compressed): sealed={compressed.sealed_search_ms:.3f} ms, "
                f"mutable={compressed.mutable_search_ms:.3f} ms"
            )
        lines.append("")

    # IVF impact
    no_ivf_compressed = indexed.get(("ivf-disabled", "compressed-hybrid"))
    ivf_compressed = indexed.get(("ivf-enabled", "compressed-hybrid"))
    if no_ivf_compressed and ivf_compressed:
        delta = ivf_compressed.latency_ms - no_ivf_compressed.latency_ms
        sign = "faster" if delta < 0 else "slower"
        lines.append(
            f"## IVF impact on compressed-hybrid\n"
            f"- {no_ivf_compressed.latency_ms:.3f} ms → {ivf_compressed.latency_ms:.3f} ms "
            f"({abs(delta):.3f} ms {sign}), candidates: "
            f"{no_ivf_compressed.candidate_count:.1f} → {ivf_compressed.candidate_count:.1f}"
        )

    return "\n".join(lines).strip() + "\n"


def _rows_for_result(
    *,
    fixture_name: str,
    quantizer_name: str,
    ivf_mode: str,
    result: object,
) -> list[Sprint5Row]:
    rows = [
        _row(fixture_name, quantizer_name, ivf_mode, result.exact),
        _row(fixture_name, quantizer_name, ivf_mode, result.compressed),
    ]
    if result.reranked is not None:
        rows.append(_row(fixture_name, quantizer_name, ivf_mode, result.reranked))
    return rows


def _row(
    fixture_name: str,
    quantizer_name: str,
    ivf_mode: str,
    result: HarnessPathResult,
) -> Sprint5Row:
    return Sprint5Row(
        fixture_name=fixture_name,
        quantizer_name=quantizer_name,
        ivf_mode=ivf_mode,
        query_path=result.path_name,
        latency_ms=result.latency_ms,
        mutable_search_ms=float(result.trace.get("mutable_search_latency_ms", 0.0)),
        sealed_search_ms=float(result.trace.get("sealed_search_latency_ms", 0.0)),
        rerank_ms=float(result.trace.get("rerank_latency_ms", 0.0)),
        recall_at_10=result.recall_at_10,
        candidate_count=float(result.trace.get("candidate_generation_count", 0.0)),
    )
