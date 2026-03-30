from __future__ import annotations

from turboquant_db.benchmark.datasets import BenchmarkDataset, BenchmarkItem


def medium_synthetic_fixture(size: int = 128) -> BenchmarkDataset:
    items: list[BenchmarkItem] = []
    for index in range(size):
        x = float((index % 16) / 15.0)
        y = float(((index * 7) % 16) / 15.0)
        items.append(
            BenchmarkItem(
                vector_id=f"doc-{index}",
                embedding=[x, y],
                metadata={
                    "bucket": index % 4,
                    "family": "alpha" if index % 2 == 0 else "beta",
                },
            )
        )

    queries = [
        [1.0, 0.0],
        [0.0, 1.0],
        [0.8, 0.2],
        [0.2, 0.8],
    ]
    return BenchmarkDataset(name=f"medium_synthetic_{size}", items=items, queries=queries)
