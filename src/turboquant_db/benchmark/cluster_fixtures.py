from __future__ import annotations

from turboquant_db.benchmark.datasets import BenchmarkDataset, BenchmarkItem


def clustered_fixture(size_per_cluster: int = 32) -> BenchmarkDataset:
    items: list[BenchmarkItem] = []
    centers = [
        (0.95, 0.05, "alpha"),
        (0.05, 0.95, "beta"),
        (0.75, 0.25, "gamma"),
    ]

    index = 0
    for cx, cy, family in centers:
        for offset in range(size_per_cluster):
            dx = ((offset % 4) - 1.5) * 0.01
            dy = (((offset // 4) % 4) - 1.5) * 0.01
            items.append(
                BenchmarkItem(
                    vector_id=f"doc-{index}",
                    embedding=[max(0.0, min(1.0, cx + dx)), max(0.0, min(1.0, cy + dy))],
                    metadata={"family": family, "cluster": family},
                )
            )
            index += 1

    queries = [
        [0.96, 0.04],
        [0.04, 0.96],
        [0.74, 0.26],
        [0.8, 0.2],
    ]
    return BenchmarkDataset(name=f"clustered_fixture_{size_per_cluster}", items=items, queries=queries)
