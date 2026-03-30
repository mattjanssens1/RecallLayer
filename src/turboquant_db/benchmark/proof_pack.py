from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable

from turboquant_db.benchmark.cluster_fixtures import clustered_fixture
from turboquant_db.benchmark.fixtures import tiny_fixture
from turboquant_db.benchmark.metrics import average_latency_ms, recall_at_k
from turboquant_db.engine.showcase_scored_db import ShowcaseScoredDatabase
from turboquant_db.quantization.scalar import ScalarQuantizer
from turboquant_db.quantization.turboquant_adapter import TurboQuantAdapter


@dataclass(slots=True)
class ProofRow:
    fixture_name: str
    query_path: str
    backend: str
    latency_ms: float
    recall_at_1: float
    recall_at_10: float
    note: str


def render_proof_markdown(rows: list[ProofRow]) -> str:
    lines = [
        "| Fixture | Query path | Backend | Latency ms | Recall@1 | Recall@10 | Note |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.fixture_name} | {row.query_path} | {row.backend} | {row.latency_ms:.3f} | {row.recall_at_1:.3f} | {row.recall_at_10:.3f} | {row.note} |"
        )
    return "\n".join(lines)


def build_proof_rows(root_prefix: str = ".proof_pack") -> list[ProofRow]:
    fixture_specs = [
        (tiny_fixture(), 2),
        (clustered_fixture(size_per_cluster=16), 5),
    ]

    rows: list[ProofRow] = []
    for fixture_index, (dataset, top_k) in enumerate(fixture_specs):
        exact_db = ShowcaseScoredDatabase(
            collection_id=f"{dataset.name}-exact-{fixture_index}",
            root_dir=f"{root_prefix}-exact-{fixture_index}",
            quantizer=ScalarQuantizer(),
        )
        for item in dataset.items:
            exact_db.upsert(vector_id=item.vector_id, embedding=item.embedding, metadata=item.metadata)
        exact_db.flush_mutable(segment_id="seg-1", generation=1)

        exact_ids, exact_latency_ms = _run_path(
            exact_db,
            dataset.queries,
            top_k=top_k,
            query_fn=lambda query: exact_db.query_exact_hybrid_hits(query, top_k=top_k),
        )
        rows.append(
            ProofRow(
                fixture_name=dataset.name,
                query_path="exact-hybrid",
                backend="exact-baseline",
                latency_ms=exact_latency_ms,
                recall_at_1=1.0,
                recall_at_10=1.0,
                note="Reference path for recall comparison.",
            )
        )

        backend_specs = [
            (ScalarQuantizer(), "scalar-quantizer", "Measured compressed scan baseline."),
            (TurboQuantAdapter(), "turboquant-adapter", "Adapter-based placeholder, not full-fidelity TurboQuant."),
        ]

        for backend_index, (quantizer, backend_name, backend_note) in enumerate(backend_specs):
            db = ShowcaseScoredDatabase(
                collection_id=f"{dataset.name}-{backend_name}-{backend_index}",
                root_dir=f"{root_prefix}-{fixture_index}-{backend_index}",
                quantizer=quantizer,
            )
            for item in dataset.items:
                db.upsert(vector_id=item.vector_id, embedding=item.embedding, metadata=item.metadata)
            db.flush_mutable(segment_id="seg-1", generation=1)

            compressed_ids, compressed_latency_ms = _run_path(
                db,
                dataset.queries,
                top_k=top_k,
                query_fn=lambda query: db.query_compressed_hybrid_hits(query, top_k=top_k),
            )
            rows.append(
                ProofRow(
                    fixture_name=dataset.name,
                    query_path="compressed-hybrid",
                    backend=backend_name,
                    latency_ms=compressed_latency_ms,
                    recall_at_1=recall_at_k(expected_ids=exact_ids, actual_ids=compressed_ids, k=1),
                    recall_at_10=recall_at_k(expected_ids=exact_ids, actual_ids=compressed_ids, k=min(10, top_k)),
                    note=backend_note,
                )
            )

            reranked_ids, reranked_latency_ms = _run_path(
                db,
                dataset.queries,
                top_k=top_k,
                query_fn=lambda query: db.query_compressed_reranked_hybrid_hits(query, top_k=top_k),
            )
            rows.append(
                ProofRow(
                    fixture_name=dataset.name,
                    query_path="compressed-reranked-hybrid",
                    backend=backend_name,
                    latency_ms=reranked_latency_ms,
                    recall_at_1=recall_at_k(expected_ids=exact_ids, actual_ids=reranked_ids, k=1),
                    recall_at_10=recall_at_k(expected_ids=exact_ids, actual_ids=reranked_ids, k=min(10, top_k)),
                    note=f"{backend_note} Includes rerank over compressed candidates.",
                )
            )

    return rows


def _run_path(
    db: ShowcaseScoredDatabase,
    queries: list[list[float]],
    *,
    top_k: int,
    query_fn: Callable[[list[float]], list[object]],
) -> tuple[list[str], float]:
    ids: list[str] = []
    samples_ms: list[float] = []
    for query in queries:
        start = perf_counter()
        hits = query_fn(query)
        samples_ms.append((perf_counter() - start) * 1000.0)
        ids.extend(hit.vector_id for hit in hits[:top_k])
    return ids, average_latency_ms(samples_ms)
