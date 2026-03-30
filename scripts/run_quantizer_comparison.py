from __future__ import annotations

from pathlib import Path

from turboquant_db.benchmark.comparison import render_markdown_table
from turboquant_db.benchmark.quantizer_compare import run_quantizer_comparison


def main() -> None:
    artifacts = run_quantizer_comparison()
    table = render_markdown_table(artifacts.rows)
    output_path = Path("reports") / "quantizer_comparison.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(table + "\n", encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
