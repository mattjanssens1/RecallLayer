from __future__ import annotations

from pathlib import Path

from turboquant_db.benchmark.comparison import render_markdown_table
from turboquant_db.benchmark.highdim_runner import run_highdim_benchmark


def main() -> None:
    artifacts = run_highdim_benchmark()
    output_path = Path("reports") / "highdim_benchmark.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_table(artifacts.rows) + "\n", encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
