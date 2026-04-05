from __future__ import annotations

from recalllayer.benchmark.datasets import BenchmarkDataset, BenchmarkItem


def xlarge_synthetic_fixture(size: int = 512) -> BenchmarkDataset:
    items: list[BenchmarkItem] = []
    for index in range(size):
        x = float((index % 32) / 31.0)
        y = float(((index * 11) % 32) / 31.0)
        items.append(
            BenchmarkItem(
                vector_id=f"doc-{index}",
                embedding=[x, y],
                metadata={
                    "bucket": index % 8,
                    "family": "alpha" if index % 3 == 0 else ("beta" if index % 3 == 1 else "gamma"),
                },
            )
        )

    queries = [
        [1.0, 0.0],
        [0.0, 1.0],
        [0.9, 0.1],
        [0.1, 0.9],
        [0.75, 0.25],
        [0.25, 0.75],
    ]
    return BenchmarkDataset(name=f"xlarge_synthetic_{size}", items=items, queries=queries)
