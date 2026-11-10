"""Run the reproducible baseline-only CareGrid forecasting experiment."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from caregrid.forecasting import run_experiment


def main() -> int:
    result = run_experiment()
    print(f"Experiment: {result['status']}")
    print(f"Readiness report: reports/forecasting_readiness_audit.md")
    print(f"Results report: reports/forecasting_experiment_report.md")
    print(json.dumps(result["evaluation_metrics"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
