from __future__ import annotations

from pathlib import Path

from turboquant_db.benchmark.comparison import render_markdown_table
from turboquant_db.benchmark.diagnostics import BenchmarkDiagnostics, write_diagnostics
from turboquant_db.benchmark.showcase_runner import run_showcase_benchmark


def main() -> None:
    artifacts = run_showcase_benchmark()
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = reports_dir / "showcase_bundle.md"
    markdown_path.write_text(render_markdown_table(artifacts.rows) + "\n", encoding="utf-8")

    diagnostics_path = write_diagnostics(
        BenchmarkDiagnostics(
            fixture_name="tiny_fixture",
            query_count=3,
            quantizer_name="showcase-scored-db",
            top_k=2,
            report_kind="showcase-bundle",
        ),
        reports_dir / "showcase_bundle.json",
    )
    print(markdown_path)
    print(diagnostics_path)


if __name__ == "__main__":
    main()
