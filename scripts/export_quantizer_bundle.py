from __future__ import annotations

from pathlib import Path

from recalllayer.benchmark.comparison import render_markdown_table
from recalllayer.benchmark.diagnostics import BenchmarkDiagnostics, write_diagnostics
from recalllayer.benchmark.quantizer_compare import run_quantizer_comparison


def main() -> None:
    artifacts = run_quantizer_comparison()
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = reports_dir / "quantizer_bundle.md"
    markdown_path.write_text(render_markdown_table(artifacts.rows) + "\n", encoding="utf-8")

    diagnostics_path = write_diagnostics(
        BenchmarkDiagnostics(
            fixture_name="tiny_fixture",
            query_count=3,
            quantizer_name="multiple",
            top_k=2,
            report_kind="quantizer-bundle",
        ),
        reports_dir / "quantizer_bundle.json",
    )
    print(markdown_path)
    print(diagnostics_path)


if __name__ == "__main__":
    main()
