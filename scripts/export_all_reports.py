from __future__ import annotations

from pathlib import Path
import subprocess
import sys


SCRIPTS = [
    "scripts/export_showcase_bundle.py",
    "scripts/export_quantizer_bundle.py",
    "scripts/export_extended_diagnostics.py",
    "scripts/export_benchmark_diagnostics.py",
    "scripts/export_quantizer_summary.py",
    "scripts/export_quantizer_details.py",
]


def main() -> None:
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    for script in SCRIPTS:
        subprocess.run([sys.executable, script], check=True)

    print(reports_dir)


if __name__ == "__main__":
    main()
