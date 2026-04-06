"""Run Sprint 5 benchmark and write results to reports/sprint5_benchmark.md."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from recalllayer.benchmark.sprint5 import build_sprint5_rows, render_sprint5_markdown, summarize_sprint5

REPORT_PATH = Path(__file__).parent.parent / "reports" / "sprint5_benchmark.md"


def main() -> None:
    print("Building Sprint 5 benchmark rows...")
    rows = build_sprint5_rows()
    table = render_sprint5_markdown(rows)
    summary = summarize_sprint5(rows)
    output = table + "\n\n---\n\n" + summary
    REPORT_PATH.write_text(output, encoding="utf-8")
    print(f"Report written to {REPORT_PATH}")
    print()
    print(summary)


if __name__ == "__main__":
    main()
