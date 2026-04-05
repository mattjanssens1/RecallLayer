from __future__ import annotations

import subprocess
import sys

COMMANDS = [
    [sys.executable, "scripts/run_showcase_benchmark.py"],
    [sys.executable, "scripts/export_proof_pack.py"],
    [sys.executable, "scripts/run_cache_sprint4_benchmark.py"],
]


def main() -> None:
    for command in COMMANDS:
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
