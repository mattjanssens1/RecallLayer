from __future__ import annotations

import subprocess
import sys


COMMANDS = [
    [sys.executable, "scripts/run_showcase_benchmark.py"],
    [sys.executable, "scripts/run_quantizer_comparison.py"],
    [sys.executable, "scripts/run_extended_benchmark.py"],
    [sys.executable, "scripts/export_all_reports.py"],
]


def main() -> None:
    for command in COMMANDS:
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
