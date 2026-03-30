from __future__ import annotations

import subprocess
import sys


SCRIPTS = [
    "scripts/export_showcase_bundle.py",
    "scripts/export_quantizer_bundle.py",
    "scripts/export_extended_diagnostics.py",
    "scripts/export_cluster_bundle.py",
    "scripts/export_xlarge_bundle.py",
    "scripts/export_highdim_bundle.py",
    "scripts/export_quantizer_summary.py",
    "scripts/export_quantizer_details.py",
    "scripts/generate_reports_index.py",
]


def main() -> None:
    for script in SCRIPTS:
        subprocess.run([sys.executable, script], check=True)


if __name__ == "__main__":
    main()
