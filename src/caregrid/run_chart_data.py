"""Generate validated, exploratory chart data from retrospective forecasts."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from caregrid.chart_data import (
    build_forecast_band_table,
    build_model_comparison,
)

CAL_PATH = Path("reports/interval_calibration/calibrated_predictions.csv")
DIRECT_PATH = Path("reports/direct_model_experiment/direct_predictions.csv")
REF_PATH = Path("reports/model_selection/model_selection_rolling_origin_2018_2023.csv")
OUT_DIR = Path("outputs/chart_data")

KEYS = ["disease", "model_name", "feature_set"]
METRICS = ["rows", "mae", "coverage_80", "coverage_95", "width_80"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_reference(bands: pd.DataFrame, ref: pd.DataFrame) -> None:
    """Validate original intervals against the 2018-2023 reference."""
    b = bands.loc[
        (bands["validation_phase"] == "rolling_origin")
        & bands["origin_period"].astype(str).between("2018-12", "2023-12")
    ].copy()

    b["abs_error"] = (b["actual"] - b["predictive_mean"]).abs()

    for level in ("80", "95"):
        lower = b[f"prediction_interval_{level}_lower"]
        upper = b[f"prediction_interval_{level}_upper"]
        b[f"coverage_{level}"] = (
            (b["actual"] >= lower) & (b["actual"] <= upper)
        ).astype(float)

    b["width_80"] = (
        b["prediction_interval_80_upper"]
        - b["prediction_interval_80_lower"]
    )

    calc = b.groupby(KEYS).agg(
        rows=("actual", "size"),
        mae=("abs_error", "mean"),
        coverage_80=("coverage_80", "mean"),
        coverage_95=("coverage_95", "mean"),
        width_80=("width_80", "mean"),
    ).reset_index()

    merged = calc.merge(
        ref[KEYS + METRICS],
        on=KEYS,
        suffixes=("_calc", "_ref"),
        validate="one_to_one",
        indicator=True,
        how="outer",
    )

    if len(merged) != len(ref) or len(ref) != 12:
        raise ValueError("Reference configuration count mismatch.")

    if not merged["_merge"].eq("both").all():
        raise ValueError("Reference model configurations do not match.")

    for metric in METRICS:
        tolerance = 0 if metric == "rows" else 0.001
        difference = (
            merged[f"{metric}_calc"] - merged[f"{metric}_ref"]
        ).abs()

        if not difference.le(tolerance).all():
            raise ValueError(
                f"Reference mismatch for {metric}: "
                f"max difference={difference.max()}"
            )

    print("REFERENCE VALIDATION PASSED: 12 configurations")


def main() -> None:
    inputs = [CAL_PATH, DIRECT_PATH, REF_PATH]

    calibrated = pd.read_csv(CAL_PATH)
    direct = pd.read_csv(DIRECT_PATH)
    reference = pd.read_csv(REF_PATH)

    bands = build_forecast_band_table(calibrated, direct)

    # Critical: validate before creating or writing output files.
    validate_reference(bands, reference)

    comparison = build_model_comparison(bands)

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    metadata = {
        "description": "Exploratory retrospective forecast chart data",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit_at_run": commit,
        "forecast_status": "backtest_only_not_future_forecasts",
        "holdout_policy": "2025 descriptive only; never used for tuning",
        "interval_policy": (
            "Display calibrated bands where available; otherwise original. "
            "Calibration does not correct biased forecast means."
        ),
        "reference_validation": "passed_12_configurations",
        "input_sha256": {str(path): sha256(path) for path in inputs},
        "output_rows": {
            "forecast_bands": len(bands),
            "model_comparison": len(comparison),
        },
        "limitations": [
            "No operational outbreak alerts or validated outbreak labels.",
            "Poisson prediction intervals are substantially too narrow.",
            "Dengue horizons 9-12 have substantial interval undercoverage.",
            "2018 and 2019 origins lack calibrated intervals.",
            "No model is declared best or operationally ready.",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    bands_path = OUT_DIR / "forecast_bands.csv"
    comparison_path = OUT_DIR / "model_comparison.csv"
    metadata_path = OUT_DIR / "chart_data_metadata.json"

    bands.to_csv(bands_path, index=False)
    comparison.to_csv(comparison_path, index=False)

    metadata["output_sha256"] = {
        str(bands_path): sha256(bands_path),
        str(comparison_path): sha256(comparison_path),
    }

    metadata_path.write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Forecast band rows: {len(bands)}")
    print(f"Model comparison rows: {len(comparison)}")

    print("\nPooled comparison (development rolling origins):")
    pooled = comparison.loc[
        (comparison["evidence_role"] == "development_rolling_origin")
        & (comparison["horizon_scope"] == "pooled")
    ]

    print(
        pooled[
            [
                "disease",
                "model_name",
                "feature_set",
                "mae",
                "coverage_80_original",
                "coverage_80_display",
                "coverage_95_display",
            ]
        ].round(3).to_string(index=False)
    )

    print("\nGenerated files:")
    for path in (bands_path, comparison_path, metadata_path):
        print(path)


if __name__ == "__main__":
    main()
