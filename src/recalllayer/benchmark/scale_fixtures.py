from __future__ import annotations

import numpy as np

from recalllayer.benchmark.datasets import BenchmarkDataset, BenchmarkItem


def scale_fixture(
    n_items: int,
    n_dims: int = 128,
    n_clusters: int = 20,
    n_queries: int = 10,
    seed: int = 42,
) -> BenchmarkDataset:
    """Generate a clustered unit-sphere dataset at arbitrary scale.

    Args:
        n_items: Number of vectors (e.g. 25_000, 50_000, 100_000).
        n_dims: Embedding dimensionality.
        n_clusters: Number of Gaussian cluster centers.
        n_queries: Number of query vectors (one per cluster up to n_clusters).
        seed: RNG seed for reproducibility.
    """
    rng = np.random.default_rng(seed)

    centers = rng.standard_normal((n_clusters, n_dims)).astype(np.float32)
    norms = np.linalg.norm(centers, axis=1, keepdims=True)
    centers /= norms

    items: list[BenchmarkItem] = []
    for i in range(n_items):
        cluster = i % n_clusters
        vec = centers[cluster] + rng.standard_normal(n_dims).astype(np.float32) * 0.1
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        items.append(
            BenchmarkItem(
                vector_id=f"vec-{i}",
                embedding=vec.tolist(),
                metadata={"cluster": cluster, "batch": i // 1000},
            )
        )

    queries: list[list[float]] = []
    for c in range(min(n_queries, n_clusters)):
        q = centers[c] + rng.standard_normal(n_dims).astype(np.float32) * 0.05
        norm = float(np.linalg.norm(q))
        if norm > 0:
            q = q / norm
        queries.append(q.tolist())

    return BenchmarkDataset(
        name=f"scale_fixture_{n_items}x{n_dims}",
        items=items,
        queries=queries,
    )
