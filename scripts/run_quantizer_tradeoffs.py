from __future__ import annotations

import json
from pathlib import Path

from recalllayer.benchmark.tradeoff_runner import (
    render_tradeoff_markdown,
    run_quantizer_tradeoff_benchmark,
    tradeoff_rows_to_dict,
)


def main() -> None:
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    rows = run_quantizer_tradeoff_benchmark(root_prefix=reports_dir / "quantizer-tradeoffs")
    markdown = render_tradeoff_markdown(rows)
    payload = tradeoff_rows_to_dict(rows)

    json_path = reports_dir / "quantizer-tradeoffs.json"
    markdown_path = reports_dir / "quantizer-tradeoffs.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown + "\n", encoding="utf-8")

    print(markdown)
    print(f"\nWrote {json_path}")
    print(f"Wrote {markdown_path}")


if __name__ == "__main__":
    main()
