"""Apply post-hoc conformal calibration to saved multi-model predictions.

Reads reports/multimodel_experiment/predictions.csv and writes ONLY to
reports/interval_calibration/. Existing results are never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from caregrid.multimodel.calibration import calibrate_predictions, summarize_calibration

DEFAULT_INPUT = PROJECT_ROOT / "reports" / "multimodel_experiment" / "predictions.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "interval_calibration"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-scores", type=int, default=28)
    args = parser.parse_args()

    target = args.output_dir / "calibrated_predictions.csv"
    if target.exists():
        print(f"Refusing to overwrite existing results: {target}")
        return 1
    predictions = pd.read_csv(args.input)
    calibrated = calibrate_predictions(predictions, min_scores=args.min_scores)
    summary = summarize_calibration(calibrated)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    calibrated.drop(columns=["experiment_spec"], errors="ignore").to_csv(target, index=False)
    summary.to_csv(args.output_dir / "calibration_summary.csv", index=False)
    metadata = {
        "method": "split conformal, relative interval score, earlier origins only",
        "min_scores": args.min_scores,
        "input_file": args.input.name,
        "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "note": "Calibration widens or narrows intervals; it does not correct biased forecast means.",
    }
    (args.output_dir / "calibration_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "status": "completed",
        "prediction_rows": int(len(calibrated)),
        "summary_rows": int(len(summary)),
        "output_dir": str(args.output_dir),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
