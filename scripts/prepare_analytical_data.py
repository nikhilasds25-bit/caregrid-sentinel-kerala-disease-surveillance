"""Prepare exploratory analytical datasets for the CareGrid API.

Run from the repository root:
    PYTHONPATH=src python scripts/prepare_analytical_data.py

Uses existing generators. Does not train forecasting models or
modify source datasets.
"""

from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

GENERATORS = [
    "caregrid.run_chart_data",
    "caregrid.run_anomaly_chart_data",
    "caregrid.run_exceedance_analysis",
    "caregrid.run_exceedance_chart_data",
]

REQUIRED_OUTPUTS = [
    "outputs/chart_data/forecast_bands.csv",
    "outputs/chart_data/model_comparison.csv",
    "outputs/anomaly_chart_data/anomaly_signals.csv",
    "outputs/exceedance_chart_data/exceedance_chart_data.csv",
]


def main():
    env = os.environ.copy()
    src = str(ROOT / "src")
    env["PYTHONPATH"] = (
        src + os.pathsep + env["PYTHONPATH"]
        if env.get("PYTHONPATH")
        else src
    )

    for module in GENERATORS:
        print(f"\nRunning {module}", flush=True)
        subprocess.run(
            [sys.executable, "-m", module],
            cwd=ROOT,
            env=env,
            check=True,
        )

    missing = [
        filename
        for filename in REQUIRED_OUTPUTS
        if not (ROOT / filename).is_file()
    ]

    if missing:
        raise SystemExit(
            "Missing required analytical datasets:\n"
            + "\n".join(missing)
        )

    print("\nAnalytical dataset preparation completed successfully.")
    print("All four required analytical CSV files are available.")


if __name__ == "__main__":
    main()
