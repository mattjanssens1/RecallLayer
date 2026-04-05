from __future__ import annotations

from recalllayer.benchmark.datasets import BenchmarkDataset, BenchmarkItem


def tiny_fixture() -> BenchmarkDataset:
    items = [
        BenchmarkItem(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us", "tier": "gold"}),
        BenchmarkItem(vector_id="b", embedding=[0.0, 1.0], metadata={"region": "ca", "tier": "silver"}),
        BenchmarkItem(vector_id="c", embedding=[0.8, 0.2], metadata={"region": "us", "tier": "platinum"}),
        BenchmarkItem(vector_id="d", embedding=[0.2, 0.8], metadata={"region": "ca", "tier": "gold"}),
    ]
    queries = [[0.9, 0.1], [0.1, 0.9], [0.75, 0.25]]
    return BenchmarkDataset(name="tiny_fixture", items=items, queries=queries)


def filter_fixture() -> BenchmarkDataset:
    items = [
        BenchmarkItem(vector_id="p1", embedding=[1.0, 0.0], metadata={"product": "payments", "priority": 3}),
        BenchmarkItem(vector_id="p2", embedding=[0.9, 0.1], metadata={"product": "payments", "priority": 1}),
        BenchmarkItem(vector_id="r1", embedding=[0.0, 1.0], metadata={"product": "risk", "priority": 3}),
        BenchmarkItem(vector_id="r2", embedding=[0.1, 0.9], metadata={"product": "risk", "priority": 1}),
    ]
    queries = [[0.95, 0.05], [0.05, 0.95]]
    return BenchmarkDataset(name="filter_fixture", items=items, queries=queries)
