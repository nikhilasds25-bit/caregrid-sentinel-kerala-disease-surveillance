"""Write exploratory Q90 exceedance thresholds, scored draws and methodology metadata.

Exploratory statistical thresholds only; not official outbreak definitions, and an
exceedance is not a confirmed outbreak. Run from the repo root:
    PYTHONPATH=src python -m caregrid.run_exceedance_analysis
Writes to outputs/exceedance_thresholds/ by default (never under reports/).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from caregrid.exceedance import (
    CALIBRATION_STATUS,
    DEFINITION_IDS,
    THRESHOLD_LABEL,
    build_threshold_table,
    score_exceedances,
)
from caregrid.outbreak_detection import load_confirmed_observations

DEFAULT_OBS = "data/candidates/kerala_district_monthly_disease_dashboard_2016_2025.csv"
DEFAULT_DRAWS = "outputs/predictive_draws/draws_200.npy"
DEFAULT_INDEX = "outputs/predictive_draws/draw_index.csv"
SCORED_COLUMNS = [
    "row_id", "disease", "district", "model_name", "validation_phase", "phase", "origin_period",
    "target_period", "horizon", "actual", "predictive_mean", "method", "threshold_definition_id",
    "threshold_label", "reference_start", "reference_end", "n_reference_values", "threshold",
    "status", "observed_exceedance", "predicted_probability", "calibration_status",
]


def _sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--observations", default=DEFAULT_OBS)
    ap.add_argument("--draws", default=DEFAULT_DRAWS)
    ap.add_argument("--draw-index", default=DEFAULT_INDEX)
    ap.add_argument("--output-dir", default="outputs/exceedance_thresholds")
    args = ap.parse_args(argv)

    out = Path(args.output_dir)
    if "reports" in out.parts:
        raise SystemExit("Refusing to write under reports/ (experiment runners overwrite it).")

    obs = load_confirmed_observations(args.observations)
    ix = pd.read_csv(args.draw_index)
    draws = np.load(args.draws)
    origins = sorted(ix["origin_period"].unique())
    th = build_threshold_table(obs, origins)

    sc = score_exceedances(ix, draws, th)
    sc["phase"] = np.where(sc["validation_phase"] == "final_2025", "holdout_2025_descriptive", "rolling_2019_2024")
    sc["calibration_status"] = CALIBRATION_STATUS

    out.mkdir(parents=True, exist_ok=True)
    th.to_csv(out / "thresholds_by_origin.csv", index=False)
    sc[SCORED_COLUMNS].to_csv(out / "exceedance_scored_draws.csv", index=False)

    meta = {
        "label": THRESHOLD_LABEL,
        "calibration_status": CALIBRATION_STATUS,
        "interpretation": "Exploratory statistical thresholds. Not official outbreak definitions. An exceedance is not a confirmed outbreak.",
        "target_definition": "Observed monthly Confirmed case count STRICTLY GREATER than the district- and disease-specific threshold.",
        "methods": {
            DEFINITION_IDS["q90_all_months"]: "90th percentile (numpy linear) of all monthly Confirmed counts for the district/disease with period <= origin.",
            DEFINITION_IDS["q90_season_window"]: "90th percentile (numpy linear) of Confirmed counts in the target calendar month +/- 1 month (circular), period <= origin. Sensitivity analysis for seasonality.",
        },
        "parameters": {"quantile": 0.9, "season_half_width": 1, "min_values_all_months": 24, "min_values_season_window": 20},
        "reference_period_rule": "Each origin uses observations from 2016-01 to the origin month only (no future data). Origin 2024-12 is used for the 2025 holdout.",
        "origins": origins,
        "draw_probability": "Share of the 200 approximate predictive draws strictly above the threshold; resolution 0.005; draws are marginal per district-month.",
        "inputs": {
            "observations": {"path": args.observations, "sha256": _sha256(args.observations)},
            "draws": {"path": args.draws, "sha256": _sha256(args.draws)},
            "draw_index": {"path": args.draw_index, "sha256": _sha256(args.draw_index)},
        },
        "code": {
            "git_commit_at_run": _git_commit(),
            "modules": ["src/caregrid/exceedance.py", "src/caregrid/run_exceedance_analysis.py"],
        },
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
        "row_counts": {
            "thresholds": int(len(th)),
            "scored_rows": int(len(sc)),
            "scored_rows_with_threshold": int((sc["status"] == "ok").sum()),
        },
        "known_limitations": [
            "Only 6 development origins and one 2025 holdout; no labelled outbreaks; thresholds not validated.",
            "Counts are non-stationary between years, so an out-of-sample Q90 exceedance rate is not 10%.",
        ],
    }
    (out / "exceedance_methodology.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"wrote {sorted(p.name for p in out.iterdir())} to {out}")
    print(f"scored rows: {len(sc)} | with threshold: {int((sc['status'] == 'ok').sum())}")


if __name__ == "__main__":
    main()
