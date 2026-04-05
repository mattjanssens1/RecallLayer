from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path


@dataclass(slots=True)
class BenchmarkDiagnostics:
    fixture_name: str
    query_count: int
    quantizer_name: str
    top_k: int
    report_kind: str


def write_diagnostics(diagnostics: BenchmarkDiagnostics, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(diagnostics), indent=2, sort_keys=True), encoding="utf-8")
    return output_path
