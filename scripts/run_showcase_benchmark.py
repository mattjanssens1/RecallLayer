from __future__ import annotations

from pathlib import Path

from recalllayer.benchmark.comparison import render_markdown_table
from recalllayer.benchmark.showcase_runner import run_showcase_benchmark


def main() -> None:
    artifacts = run_showcase_benchmark()
    table = render_markdown_table(artifacts.rows)
    output_path = Path("reports") / "showcase_benchmark.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(table + "\n", encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
