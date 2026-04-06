from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from recalllayer.benchmark.generated_fixtures import medium_synthetic_fixture
from recalllayer.benchmark.mini_harness import run_mini_harness
from recalllayer.engine.showcase_scored_db import ShowcaseScoredDatabase
from recalllayer.quantization.base import Quantizer
from recalllayer.quantization.experiments import NormalizedScalarQuantizer, ShiftedTurboQuantAdapter
from recalllayer.quantization.scalar import ScalarQuantizer
from recalllayer.quantization.turboquant_adapter import TurboQuantAdapter


@dataclass(slots=True)
class TradeoffRow:
    quantizer: str
    search_budget: int | None
    exact_latency_ms: float
    compressed_latency_ms: float
    compressed_recall_at_1: float
    compressed_recall_at_10: float
    reranked_latency_ms: float | None
    reranked_recall_at_10: float | None
    storage_bytes: int
    bytes_per_vector: float


DEFAULT_QUANTIZERS: tuple[Quantizer, ...] = (
    ScalarQuantizer(),
    NormalizedScalarQuantizer(),
    TurboQuantAdapter(),
    ShiftedTurboQuantAdapter(),
)

DEFAULT_SEARCH_BUDGETS: tuple[int | None, ...] = (None, 16, 32)


def run_quantizer_tradeoff_benchmark(
    *,
    root_prefix: str | Path = ".quantizer-tradeoffs",
    quantizers: tuple[Quantizer, ...] | list[Quantizer] = DEFAULT_QUANTIZERS,
    search_budgets: tuple[int | None, ...] | list[int | None] = DEFAULT_SEARCH_BUDGETS,
) -> list[TradeoffRow]:
    dataset = medium_synthetic_fixture(size=256)
    rows: list[TradeoffRow] = []
    root_prefix = Path(root_prefix)

    for quantizer_index, quantizer in enumerate(quantizers):
        for budget_index, search_budget in enumerate(search_budgets):
            scenario_root = root_prefix / f"{quantizer_index}-{budget_index}-{quantizer.name}"
            row = _run_tradeoff_case(
                quantizer=quantizer,
                dataset=dataset,
                root_dir=scenario_root,
                search_budget=search_budget,
            )
            rows.append(row)
    return rows


def _run_tradeoff_case(
    *,
    quantizer: Quantizer,
    dataset,
    root_dir: Path | None = None,
    search_budget: int | None,
) -> TradeoffRow:
    if root_dir is None:
        with TemporaryDirectory(prefix="recalllayer-tradeoff-") as temp_dir:
            return _run_tradeoff_case(
                quantizer=quantizer,
                dataset=dataset,
                root_dir=Path(temp_dir),
                search_budget=search_budget,
            )

    db = ShowcaseScoredDatabase(
        collection_id=f"{dataset.name}-{quantizer.name}-{search_budget}",
        root_dir=root_dir,
        quantizer=quantizer,
        enable_ivf=True,
        ivf_n_clusters=8,
        ivf_probe_k=2,
        rerank_probe_k=4,
        enable_segment_cache=False,
    )
    for item in dataset.items:
        db.upsert(vector_id=item.vector_id, embedding=item.embedding, metadata=item.metadata)
    db.flush_mutable(segment_id="seg-1", generation=1)

    exact = _run_exact_path(db, dataset.queries, top_k=5)
    compressed = _run_compressed_path(db, dataset.queries, top_k=5, search_budget=search_budget)
    reranked = _run_reranked_path(db, dataset.queries, top_k=5, search_budget=search_budget)
    stats = db.collection_stats()
    live_rows = int(stats["total_live_rows"])
    storage_bytes = int(stats["storage_bytes"])

    return TradeoffRow(
        quantizer=quantizer.name,
        search_budget=search_budget,
        exact_latency_ms=exact.exact_elapsed_ms,
        compressed_latency_ms=compressed.compressed_elapsed_ms,
        compressed_recall_at_1=compressed.recall_at_1,
        compressed_recall_at_10=compressed.recall_at_10,
        reranked_latency_ms=reranked.reranked.latency_ms if reranked.reranked is not None else None,
        reranked_recall_at_10=(
            reranked.reranked.recall_at_10 if reranked.reranked is not None else None
        ),
        storage_bytes=storage_bytes,
        bytes_per_vector=(storage_bytes / live_rows) if live_rows else 0.0,
    )


def _run_exact_path(db: ShowcaseScoredDatabase, queries: list[list[float]], *, top_k: int):
    return run_mini_harness(db, queries, top_k=top_k)


def _run_compressed_path(
    db: ShowcaseScoredDatabase,
    queries: list[list[float]],
    *,
    top_k: int,
    search_budget: int | None,
):
    original = db.query_compressed_hybrid_hits

    def patched(query, *, top_k):
        return original(query, top_k=top_k, search_budget=search_budget)

    db.query_compressed_hybrid_hits = patched  # type: ignore[method-assign]
    try:
        return run_mini_harness(db, queries, top_k=top_k)
    finally:
        db.query_compressed_hybrid_hits = original  # type: ignore[method-assign]


def _run_reranked_path(
    db: ShowcaseScoredDatabase,
    queries: list[list[float]],
    *,
    top_k: int,
    search_budget: int | None,
):
    original = db.query_compressed_reranked_hybrid_hits

    def patched(query, *, top_k):
        return original(query, top_k=top_k, search_budget=search_budget)

    db.query_compressed_reranked_hybrid_hits = patched  # type: ignore[method-assign]
    try:
        return run_mini_harness(db, queries, top_k=top_k)
    finally:
        db.query_compressed_reranked_hybrid_hits = original  # type: ignore[method-assign]


def render_tradeoff_markdown(rows: list[TradeoffRow]) -> str:
    lines = [
        "| Quantizer | Search budget | Exact ms | Compressed ms | Comp R@1 | Comp R@10 | Reranked ms | Reranked R@10 | Storage bytes | Bytes/vector |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {quantizer} | {budget} | {exact_ms:.3f} | {compressed_ms:.3f} | {comp_r1:.3f} | {comp_r10:.3f} | {reranked_ms} | {reranked_r10} | {storage_bytes} | {bytes_per_vector:.2f} |".format(
                quantizer=row.quantizer,
                budget=row.search_budget if row.search_budget is not None else "auto",
                exact_ms=row.exact_latency_ms,
                compressed_ms=row.compressed_latency_ms,
                comp_r1=row.compressed_recall_at_1,
                comp_r10=row.compressed_recall_at_10,
                reranked_ms=(f"{row.reranked_latency_ms:.3f}" if row.reranked_latency_ms is not None else "-"),
                reranked_r10=(f"{row.reranked_recall_at_10:.3f}" if row.reranked_recall_at_10 is not None else "-"),
                storage_bytes=row.storage_bytes,
                bytes_per_vector=row.bytes_per_vector,
            )
        )
    return "\n".join(lines)


def tradeoff_rows_to_dict(rows: list[TradeoffRow]) -> list[dict[str, object]]:
    return [asdict(row) for row in rows]
