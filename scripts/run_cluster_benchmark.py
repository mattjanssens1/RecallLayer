from __future__ import annotations

from pathlib import Path

from recalllayer.benchmark.cluster_runner import run_cluster_benchmark
from recalllayer.benchmark.comparison import render_markdown_table


def main() -> None:
    artifacts = run_cluster_benchmark()
    output_path = Path("reports") / "cluster_benchmark.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_table(artifacts.rows) + "\n", encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
