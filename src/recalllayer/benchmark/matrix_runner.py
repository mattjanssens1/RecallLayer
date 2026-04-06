from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from recalllayer.benchmark.mini_harness import HarnessResult, run_mini_harness
from recalllayer.engine.showcase_scored_db import ShowcaseScoredDatabase
from recalllayer.quantization.base import Quantizer
from recalllayer.quantization.scalar import ScalarQuantizer


@dataclass(slots=True)
class BenchmarkScenario:
    name: str
    size: int
    dimensions: int
    query_count: int
    top_k: int = 10
    shard_count: int = 1
    delete_ratio: float = 0.0
    enable_ivf: bool = True
    ivf_n_clusters: int = 8
    ivf_probe_k: int = 2
    rerank_probe_k: int | None = None


@dataclass(slots=True)
class PathMetrics:
    latency_ms: float
    recall_at_1: float
    recall_at_10: float
    trace: dict[str, object]
    cache_stats: dict[str, object]


@dataclass(slots=True)
class BenchmarkScenarioResult:
    scenario: BenchmarkScenario
    exact: PathMetrics
    compressed: PathMetrics
    reranked: PathMetrics | None
    storage_bytes: int
    live_rows: int
    deleted_rows: int

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario": asdict(self.scenario),
            "exact": asdict(self.exact),
            "compressed": asdict(self.compressed),
            "reranked": asdict(self.reranked) if self.reranked is not None else None,
            "storage_bytes": self.storage_bytes,
            "live_rows": self.live_rows,
            "deleted_rows": self.deleted_rows,
        }


DEFAULT_MATRIX: tuple[BenchmarkScenario, ...] = (
    BenchmarkScenario(
        name="small-2d-single-shard",
        size=128,
        dimensions=2,
        query_count=8,
        shard_count=1,
        delete_ratio=0.0,
        enable_ivf=False,
    ),
    BenchmarkScenario(
        name="medium-16d-ivf",
        size=512,
        dimensions=16,
        query_count=16,
        shard_count=1,
        delete_ratio=0.0,
        enable_ivf=True,
        ivf_n_clusters=16,
        ivf_probe_k=2,
        rerank_probe_k=4,
    ),
    BenchmarkScenario(
        name="medium-16d-ivf-deletes",
        size=512,
        dimensions=16,
        query_count=16,
        shard_count=2,
        delete_ratio=0.2,
        enable_ivf=True,
        ivf_n_clusters=16,
        ivf_probe_k=2,
        rerank_probe_k=6,
    ),
    BenchmarkScenario(
        name="large-32d-ivf-multishard",
        size=1024,
        dimensions=32,
        query_count=24,
        shard_count=4,
        delete_ratio=0.1,
        enable_ivf=True,
        ivf_n_clusters=32,
        ivf_probe_k=3,
        rerank_probe_k=8,
    ),
)


@dataclass(slots=True)
class ScenarioDataset:
    items: list[tuple[str, list[float], dict[str, object], str]]
    queries: list[list[float]]
    deleted_ids: set[str]


def generate_scenario_dataset(scenario: BenchmarkScenario, *, seed: int = 7) -> ScenarioDataset:
    rng = np.random.default_rng(seed)
    cluster_count = max(2, min(scenario.ivf_n_clusters, scenario.size, 32))
    centroids = rng.standard_normal((cluster_count, scenario.dimensions)).astype(np.float32)
    centroids /= np.linalg.norm(centroids, axis=1, keepdims=True)

    items: list[tuple[str, list[float], dict[str, object], str]] = []
    deleted_ids: set[str] = set()
    delete_every = None
    if scenario.delete_ratio > 0:
        delete_every = max(1, round(1.0 / scenario.delete_ratio))

    for index in range(scenario.size):
        cluster_id = index % cluster_count
        shard_id = f"shard-{index % scenario.shard_count}"
        noise = rng.standard_normal(scenario.dimensions).astype(np.float32) * 0.03
        vector = centroids[cluster_id] + noise
        norm = float(np.linalg.norm(vector))
        if norm == 0.0:
            vector = centroids[cluster_id].copy()
            norm = float(np.linalg.norm(vector))
        vector /= norm
        vector_id = f"vec-{index}"
        metadata = {
            "cluster": cluster_id,
            "family": f"f-{cluster_id % 4}",
            "shard": shard_id,
            "ordinal": index,
        }
        items.append((vector_id, vector.astype(np.float32).tolist(), metadata, shard_id))
        if delete_every is not None and (index + 1) % delete_every == 0:
            deleted_ids.add(vector_id)

    queries: list[list[float]] = []
    for query_index in range(scenario.query_count):
        base = centroids[query_index % cluster_count].copy()
        if cluster_count > 1 and query_index % 3 == 0:
            base = (base + centroids[(query_index + 1) % cluster_count]) / 2.0
        noise = rng.standard_normal(scenario.dimensions).astype(np.float32) * 0.01
        query = base + noise
        query /= float(np.linalg.norm(query))
        queries.append(query.astype(np.float32).tolist())

    return ScenarioDataset(items=items, queries=queries, deleted_ids=deleted_ids)


def run_benchmark_scenario(
    scenario: BenchmarkScenario,
    *,
    root_dir: str | Path | None = None,
    quantizer: Quantizer | None = None,
) -> BenchmarkScenarioResult:
    dataset = generate_scenario_dataset(scenario)
    quantizer = quantizer or ScalarQuantizer()

    if root_dir is None:
        with TemporaryDirectory(prefix="recalllayer-benchmark-") as temp_dir:
            return _run_benchmark_scenario_with_root(
                scenario,
                dataset=dataset,
                root_dir=Path(temp_dir),
                quantizer=quantizer,
            )
    return _run_benchmark_scenario_with_root(
        scenario,
        dataset=dataset,
        root_dir=Path(root_dir),
        quantizer=quantizer,
    )


def _run_benchmark_scenario_with_root(
    scenario: BenchmarkScenario,
    *,
    dataset: ScenarioDataset,
    root_dir: Path,
    quantizer: Quantizer,
) -> BenchmarkScenarioResult:
    db = ShowcaseScoredDatabase(
        collection_id=scenario.name,
        root_dir=root_dir,
        quantizer=quantizer,
        enable_segment_cache=False,
        enable_ivf=scenario.enable_ivf,
        ivf_n_clusters=scenario.ivf_n_clusters,
        ivf_probe_k=scenario.ivf_probe_k,
        rerank_probe_k=scenario.rerank_probe_k,
    )

    for vector_id, embedding, metadata, shard_id in dataset.items:
        db.upsert(vector_id=vector_id, embedding=embedding, metadata=metadata, shard_id=shard_id)

    for deleted_id in sorted(dataset.deleted_ids):
        shard_suffix = int(deleted_id.split("-")[-1]) % scenario.shard_count
        db.delete(vector_id=deleted_id, shard_id=f"shard-{shard_suffix}")

    for shard_index in range(scenario.shard_count):
        db.flush_mutable(
            shard_id=f"shard-{shard_index}",
            segment_id=f"seg-{shard_index + 1}",
            generation=shard_index + 1,
        )

    harness = run_mini_harness(db, dataset.queries, top_k=scenario.top_k)
    stats = db.collection_stats()
    live_rows = int(stats["total_live_rows"])
    deleted_rows = len(dataset.deleted_ids)

    return BenchmarkScenarioResult(
        scenario=scenario,
        exact=_path_metrics_from_harness(harness.exact),
        compressed=_path_metrics_from_harness(harness.compressed),
        reranked=(
            _path_metrics_from_harness(harness.reranked) if harness.reranked is not None else None
        ),
        storage_bytes=int(stats["storage_bytes"]),
        live_rows=live_rows,
        deleted_rows=deleted_rows,
    )


def run_benchmark_matrix(
    scenarios: list[BenchmarkScenario] | tuple[BenchmarkScenario, ...] = DEFAULT_MATRIX,
    *,
    root_prefix: str | Path = ".benchmark-matrix",
    quantizer: Quantizer | None = None,
) -> list[BenchmarkScenarioResult]:
    quantizer = quantizer or ScalarQuantizer()
    root_prefix = Path(root_prefix)
    results: list[BenchmarkScenarioResult] = []
    for index, scenario in enumerate(scenarios):
        scenario_root = root_prefix / f"scenario-{index}-{scenario.name}"
        results.append(
            run_benchmark_scenario(
                scenario,
                root_dir=scenario_root,
                quantizer=quantizer,
            )
        )
    return results


def render_matrix_markdown(results: list[BenchmarkScenarioResult]) -> str:
    lines = [
        "| Scenario | Size | Dim | Shards | Delete % | Exact ms | Compressed ms | Compressed R@1 | Compressed R@10 | Reranked ms | Reranked R@10 | Storage bytes |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        reranked_latency = f"{result.reranked.latency_ms:.3f}" if result.reranked else "-"
        reranked_recall = f"{result.reranked.recall_at_10:.3f}" if result.reranked else "-"
        lines.append(
            "| {name} | {size} | {dim} | {shards} | {delete_pct:.1f} | {exact_ms:.3f} | {compressed_ms:.3f} | {compressed_r1:.3f} | {compressed_r10:.3f} | {reranked_ms} | {reranked_r10} | {storage_bytes} |".format(
                name=result.scenario.name,
                size=result.scenario.size,
                dim=result.scenario.dimensions,
                shards=result.scenario.shard_count,
                delete_pct=result.scenario.delete_ratio * 100.0,
                exact_ms=result.exact.latency_ms,
                compressed_ms=result.compressed.latency_ms,
                compressed_r1=result.compressed.recall_at_1,
                compressed_r10=result.compressed.recall_at_10,
                reranked_ms=reranked_latency,
                reranked_r10=reranked_recall,
                storage_bytes=result.storage_bytes,
            )
        )
    return "\n".join(lines)


def _path_metrics_from_harness(result: HarnessResult | object) -> PathMetrics:
    path_result = result
    return PathMetrics(
        latency_ms=float(path_result.latency_ms),
        recall_at_1=float(path_result.recall_at_1),
        recall_at_10=float(path_result.recall_at_10),
        trace=dict(getattr(path_result, "trace", {})),
        cache_stats=dict(getattr(path_result, "cache_stats", {})),
    )
