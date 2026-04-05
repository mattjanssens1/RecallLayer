from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(slots=True)
class BenchmarkSummary:
    backend: str
    query_count: int
    elapsed_ms: float
    recall_at_10: float | None = None


def write_summary(summary: BenchmarkSummary, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(summary), indent=2, sort_keys=True), encoding="utf-8")
    return output_path
