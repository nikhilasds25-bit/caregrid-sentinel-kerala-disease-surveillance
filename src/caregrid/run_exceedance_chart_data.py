"""Prepare exploratory exceedance probabilities for dashboard charts."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

INPUT = Path("outputs/exceedance_thresholds/exceedance_scored_draws.csv")
OUTPUT = Path("outputs/exceedance_chart_data")

COLUMNS = [
    "disease", "district", "model_name",
    "validation_phase", "origin_period", "target_period",
    "horizon", "actual", "predictive_mean",
    "method", "threshold_definition_id", "threshold_label",
    "reference_start", "reference_end", "n_reference_values",
    "threshold", "status", "observed_exceedance",
    "predicted_probability", "calibration_status",
]

EVIDENCE_ROLES = {
    "rolling_origin": "development_rolling_origin",
    "final_2025": "holdout_descriptive_only",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    df = pd.read_csv(INPUT)

    missing = sorted(set(COLUMNS) - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if len(df) != 9408:
        raise ValueError(f"Unexpected input count: {len(df)}")

    if not df["validation_phase"].isin(EVIDENCE_ROLES).all():
        raise ValueError("Unknown validation phase")

    if not df["status"].isin(["ok", "insufficient_reference"]).all():
        raise ValueError("Unexpected threshold status")

    chart = df[COLUMNS].copy()

    chart["evidence_role"] = chart["validation_phase"].map(
        EVIDENCE_ROLES
    )

    chart["exploratory_label"] = (
        "historical_threshold_exceedance_not_outbreak_probability"
    )

    # Do not treat unavailable probabilities as zero.
    unavailable = chart["status"] != "ok"

    if chart.loc[
        unavailable,
        ["threshold", "predicted_probability", "observed_exceedance"],
    ].notna().any().any():
        raise ValueError("Unavailable rows contain calculated results")

    if chart.loc[
        ~unavailable,
        ["threshold", "predicted_probability", "observed_exceedance"],
    ].isna().any().any():
        raise ValueError("Usable rows contain missing results")

    probabilities = chart.loc[~unavailable, "predicted_probability"]

    if not probabilities.between(0, 1).all():
        raise ValueError("Probability outside [0,1]")

    chart = chart.sort_values(
        [
            "disease", "district", "origin_period",
            "target_period", "model_name", "method",
        ]
    ).reset_index(drop=True)

    summary = (
        chart.groupby(
            ["disease", "method", "evidence_role", "status"],
            dropna=False,
        )
        .agg(
            records=("target_period", "size"),
            mean_predicted_probability=(
                "predicted_probability", "mean"
            ),
            observed_exceedance_rate=(
                "observed_exceedance", "mean"
            ),
        )
        .reset_index()
    )

    metadata = {
        "description": "Exploratory historical threshold exceedance charts",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit_at_run": subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
        ).strip(),
        "input_sha256": {str(INPUT): sha256(INPUT)},
        "total_rows": len(chart),
        "usable_rows": int((~unavailable).sum()),
        "unavailable_rows": int(unavailable.sum()),
        "holdout_policy": "2025 descriptive only; not used for tuning",
        "probability_status": "uncalibrated_exploratory",
        "interpretation": (
            "Probability of exceeding an exploratory historical "
            "case-count threshold; not a validated outbreak probability."
        ),
        "missing_value_policy": (
            "Insufficient-reference probabilities remain unavailable."
        ),
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)

    chart_path = OUTPUT / "exceedance_chart_data.csv"
    summary_path = OUTPUT / "exceedance_summary.csv"
    metadata_path = OUTPUT / "exceedance_chart_metadata.json"

    chart.to_csv(chart_path, index=False)
    summary.to_csv(summary_path, index=False)

    metadata["output_sha256"] = {
        str(chart_path): sha256(chart_path),
        str(summary_path): sha256(summary_path),
    }

    metadata_path.write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )

    print("EXCEEDANCE CHART DATA GENERATED")
    print("Total rows:", len(chart))
    print("Usable rows:", int((~unavailable).sum()))
    print("Unavailable rows:", int(unavailable.sum()))

    print("\nGenerated files:")
    for path in (chart_path, summary_path, metadata_path):
        print(path)


if __name__ == "__main__":
    main()
