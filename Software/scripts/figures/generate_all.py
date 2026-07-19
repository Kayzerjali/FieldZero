"""
Master figure generation script.

Run this to regenerate all figures in docs/. Every figure in the documentation
must be produced by a sub-script called from here — no manual figure creation.

Usage:
    python scripts/figures/generate_all.py

Exit code 0 if all figures generated successfully, non-zero otherwise.
"""

import subprocess
import sys
from pathlib import Path

FIGURES_DIR = Path(__file__).parent
FIGURE_SCRIPTS: list[Path] = [
    # Add figure scripts here as they are written, e.g.:
    # FIGURES_DIR / "fig_characterisation_drift.py",
    # FIGURES_DIR / "fig_noise_budget.py",
]


def main():
    if not FIGURE_SCRIPTS:
        print("No figure scripts registered yet. Add them to FIGURE_SCRIPTS in this file.")
        return 0

    errors = []
    for script in FIGURE_SCRIPTS:
        print(f"Running {script.name} ...", end=" ", flush=True)
        result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
        if result.returncode == 0:
            print("OK")
        else:
            print("FAILED")
            errors.append((script.name, result.stderr))

    if errors:
        print(f"\n{len(errors)} figure script(s) failed:")
        for name, err in errors:
            print(f"\n--- {name} ---\n{err}")
        return 1

    print(f"\nAll {len(FIGURE_SCRIPTS)} figure scripts completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
