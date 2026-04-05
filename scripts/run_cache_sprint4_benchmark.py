from __future__ import annotations

from pathlib import Path

from recalllayer.benchmark.cache_sprint4 import (
    build_cache_sprint4_rows,
    render_cache_sprint4_markdown,
    summarize_cache_sprint4,
)


def main() -> None:
    rows = build_cache_sprint4_rows()
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    benchmark_path = reports_dir / "cache_sprint4_benchmark.md"
    summary_path = Path("docs") / "benchmark-cache-sprint-4.md"
    benchmark_path.write_text(render_cache_sprint4_markdown(rows) + "\n", encoding="utf-8")
    summary_path.write_text(summarize_cache_sprint4(rows), encoding="utf-8")
    print(benchmark_path)
    print(summary_path)


if __name__ == "__main__":
    main()
