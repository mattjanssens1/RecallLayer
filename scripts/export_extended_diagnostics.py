from __future__ import annotations

from pathlib import Path

from turboquant_db.benchmark.comparison import render_markdown_table
from turboquant_db.benchmark.diagnostics import BenchmarkDiagnostics, write_diagnostics
from turboquant_db.benchmark.extended_runner import run_extended_benchmark


def main() -> None:
    artifacts = run_extended_benchmark()
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = reports_dir / "extended_benchmark_diagnostics.md"
    markdown_path.write_text(render_markdown_table(artifacts.rows) + "\n", encoding="utf-8")

    diagnostics = BenchmarkDiagnostics(
        fixture_name=artifacts.fixture_name,
        query_count=artifacts.query_count,
        quantizer_name="multiple",
        top_k=5,
        report_kind="extended-benchmark",
    )
    diagnostics_path = write_diagnostics(diagnostics, reports_dir / "extended_benchmark_diagnostics.json")
    print(markdown_path)
    print(diagnostics_path)


if __name__ == "__main__":
    main()
