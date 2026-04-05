from __future__ import annotations

import json
from pathlib import Path

from turboquant_db.benchmark.datasets import BenchmarkDataset, BenchmarkItem


def load_fixture(path: str | Path) -> BenchmarkDataset:
    fixture_path = Path(path)
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    items = [
        BenchmarkItem(
            vector_id=item["vector_id"],
            embedding=item["embedding"],
            metadata=item.get("metadata", {}),
        )
        for item in payload["items"]
    ]
    return BenchmarkDataset(name=payload["name"], items=items, queries=payload["queries"])
