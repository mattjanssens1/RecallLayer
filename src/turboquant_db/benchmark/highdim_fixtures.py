from __future__ import annotations

from turboquant_db.benchmark.datasets import BenchmarkDataset, BenchmarkItem


def highdim_fixture(size: int = 256, dim: int = 8) -> BenchmarkDataset:
    items: list[BenchmarkItem] = []
    for index in range(size):
        vector = [float(((index * (j + 3)) % 17) / 16.0) for j in range(dim)]
        items.append(
            BenchmarkItem(
                vector_id=f"doc-{index}",
                embedding=vector,
                metadata={
                    "bucket": index % 8,
                    "family": "alpha" if index % 2 == 0 else "beta",
                    "dim": dim,
                },
            )
        )

    queries = [
        [1.0 if i == 0 else 0.0 for i in range(dim)],
        [1.0 if i == 1 else 0.0 for i in range(dim)],
        [0.5 if i < 2 else 0.0 for i in range(dim)],
        [0.25 if i < 4 else 0.0 for i in range(dim)],
    ]
    return BenchmarkDataset(name=f"highdim_fixture_{size}x{dim}", items=items, queries=queries)
