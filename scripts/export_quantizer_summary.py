from __future__ import annotations

import json
from pathlib import Path

from recalllayer.benchmark.comparison import render_markdown_table
from recalllayer.benchmark.quantizer_compare import run_quantizer_comparison


def main() -> None:
    artifacts = run_quantizer_comparison()
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = reports_dir / "quantizer_summary.md"
    markdown_path.write_text(render_markdown_table(artifacts.rows) + "\n", encoding="utf-8")

    json_path = reports_dir / "quantizer_summary.json"
    json_path.write_text(
        json.dumps(
            [
                {
                    "name": row.name,
                    "latency_ms": row.latency_ms,
                    "recall_at_1": row.recall_at_1,
                    "recall_at_10": row.recall_at_10,
                }
                for row in artifacts.rows
            ],
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(markdown_path)
    print(json_path)


if __name__ == "__main__":
    main()
