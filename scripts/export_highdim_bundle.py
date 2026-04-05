from __future__ import annotations

from pathlib import Path

from recalllayer.benchmark.comparison import render_markdown_table
from recalllayer.benchmark.diagnostics import BenchmarkDiagnostics, write_diagnostics
from recalllayer.benchmark.highdim_runner import run_highdim_benchmark


def main() -> None:
    artifacts = run_highdim_benchmark()
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = reports_dir / "highdim_bundle.md"
    markdown_path.write_text(render_markdown_table(artifacts.rows) + "\n", encoding="utf-8")

    diagnostics_path = write_diagnostics(
        BenchmarkDiagnostics(
            fixture_name=artifacts.fixture_name,
            query_count=artifacts.query_count,
            quantizer_name="multiple",
            top_k=10,
            report_kind="highdim-bundle",
        ),
        reports_dir / "highdim_bundle.json",
    )
    print(markdown_path)
    print(diagnostics_path)


if __name__ == "__main__":
    main()
