from __future__ import annotations

from pathlib import Path

REPORTS = [
    "showcase_bundle.md",
    "quantizer_bundle.md",
    "quantizer_summary.md",
    "extended_benchmark_diagnostics.md",
    "cluster_bundle.md",
    "xlarge_bundle.md",
    "highdim_bundle.md",
]


def main() -> None:
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    lines = ["# Reports Index", "", "Generated benchmark/report artifacts:", ""]
    for name in REPORTS:
        lines.append(f"- `{name}`")
    lines.append("")
    (reports_dir / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(reports_dir / "INDEX.md")


if __name__ == "__main__":
    main()
