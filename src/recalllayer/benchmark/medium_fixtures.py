from __future__ import annotations

import numpy as np

from recalllayer.benchmark.datasets import BenchmarkDataset, BenchmarkItem


def medium_fixture(
    n_items: int = 5000,
    n_dims: int = 128,
    n_clusters: int = 10,
    n_queries: int = 10,
) -> BenchmarkDataset:
    """5k-vector, 128-dim fixture for benchmarking compressed vs exact at realistic scale.

    Vectors are drawn from Gaussian clusters on the unit sphere so dot-product
    similarity is meaningful and clustered enough for IVF to help.
    """
    rng = np.random.default_rng(42)

    # Unit-sphere cluster centers
    centers = rng.standard_normal((n_clusters, n_dims)).astype(np.float32)
    centers /= np.linalg.norm(centers, axis=1, keepdims=True)

    items: list[BenchmarkItem] = []
    for i in range(n_items):
        cluster = i % n_clusters
        vec = centers[cluster] + rng.standard_normal(n_dims).astype(np.float32) * 0.1
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        items.append(
            BenchmarkItem(
                vector_id=f"vec-{i}",
                embedding=vec.tolist(),
                metadata={"cluster": cluster, "batch": i // 100},
            )
        )

    # Query vectors near each cluster center with small perturbation
    queries: list[list[float]] = []
    for c in range(min(n_queries, n_clusters)):
        q = centers[c] + rng.standard_normal(n_dims).astype(np.float32) * 0.05
        norm = np.linalg.norm(q)
        if norm > 0:
            q = q / norm
        queries.append(q.tolist())

    return BenchmarkDataset(
        name=f"medium_fixture_{n_items}x{n_dims}", items=items, queries=queries
    )
