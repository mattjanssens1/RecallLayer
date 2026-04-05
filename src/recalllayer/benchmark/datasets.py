from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class BenchmarkItem:
    vector_id: str
    embedding: list[float]
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class BenchmarkDataset:
    name: str
    items: list[BenchmarkItem]
    queries: list[list[float]]
