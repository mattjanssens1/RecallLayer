from __future__ import annotations

import json
from pathlib import Path

from recalllayer.benchmark.quantizer_compare import run_quantizer_comparison


def main() -> None:
    artifacts = run_quantizer_comparison()
    reports_dir = Path("reports") / "quantizers"
    reports_dir.mkdir(parents=True, exist_ok=True)

    for row in artifacts.rows:
        safe_name = row.name.replace("/", "-")
        output_path = reports_dir / f"{safe_name}.json"
        output_path.write_text(
            json.dumps(
                {
                    "name": row.name,
                    "latency_ms": row.latency_ms,
                    "recall_at_1": row.recall_at_1,
                    "recall_at_10": row.recall_at_10,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        print(output_path)


if __name__ == "__main__":
    main()
