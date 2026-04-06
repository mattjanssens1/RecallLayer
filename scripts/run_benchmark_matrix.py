from __future__ import annotations

import json
from pathlib import Path

from recalllayer.benchmark.matrix_runner import DEFAULT_MATRIX, render_matrix_markdown, run_benchmark_matrix


def main() -> None:
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    results = run_benchmark_matrix(DEFAULT_MATRIX, root_prefix=reports_dir / "benchmark-matrix")
    payload = [result.to_dict() for result in results]
    markdown = render_matrix_markdown(results)

    json_path = reports_dir / "benchmark-matrix.json"
    markdown_path = reports_dir / "benchmark-matrix.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown + "\n", encoding="utf-8")

    print(markdown)
    print(f"\nWrote {json_path}")
    print(f"Wrote {markdown_path}")


if __name__ == "__main__":
    main()
