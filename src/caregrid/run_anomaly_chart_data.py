"""Generate exploratory retrospective EWMA/CUSUM chart data."""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from caregrid.outbreak_detection import (
    CusumDetector,
    EwmaDetector,
    load_confirmed_observations,
)

INPUT = Path(
    "data/candidates/"
    "kerala_district_monthly_disease_dashboard_2016_2025.csv"
)
OUTPUT = Path("outputs/anomaly_chart_data")
BASELINE_PERIOD = ("2016-01", "2018-12")
DEVELOPMENT_END = "2024-12"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    observations = load_confirmed_observations(INPUT)

    # Exclude the 2025 holdout from this development output.
    development = observations.loc[
        observations["period"] <= DEVELOPMENT_END
    ].copy()

    frames = []

    for detector in (EwmaDetector(), CusumDetector()):
        records = detector.detect(
            development,
            baseline_period=BASELINE_PERIOD,
        )

        frame = pd.DataFrame([asdict(r) for r in records])
        frames.append(frame)

    result = pd.concat(frames, ignore_index=True)

    result["evidence_role"] = "development_retrospective"
    result["signal_status"] = "exploratory_unvalidated"
    result["signal_type"] = "retrospective_unusual_activity"

    result = result.sort_values(
        ["disease", "district", "period", "detector_id"]
    ).reset_index(drop=True)

    # Validate expected district-month coverage.
    assert len(result) == 4032, "Unexpected record count"
    assert result["district"].nunique() == 14
    assert result["disease"].nunique() == 2
    assert result["period"].min() == "2019-01"
    assert result["period"].max() == "2024-12"
    assert not result.duplicated(
        ["detector_id", "disease", "district", "period"]
    ).any()

    counts = result.groupby("detector_id").agg(
        records=("period", "size"),
        flagged_months=("unusual_activity_flag", "sum"),
    ).reset_index()

    assert counts["records"].eq(2016).all()
    assert len(counts) == 2

    metadata = {
        "description": "Exploratory retrospective unusual-activity chart data",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit_at_run": subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
        ).strip(),
        "input_sha256": {str(INPUT): sha256(INPUT)},
        "baseline_period": list(BASELINE_PERIOD),
        "development_period": ["2019-01", DEVELOPMENT_END],
        "holdout_policy": "2025 excluded from development output",
        "detectors": [
            "ewma_sqrt_seasonal_median_v1",
            "cusum_sqrt_seasonal_median_v1",
        ],
        "parameter_policy": "Existing untuned detector defaults",
        "interpretation": (
            "Retrospective statistical unusual-activity signals only; "
            "not validated outbreaks or operational alerts."
        ),
        "output_rows": len(result),
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)

    signals_path = OUTPUT / "anomaly_signals.csv"
    summary_path = OUTPUT / "anomaly_summary.csv"
    metadata_path = OUTPUT / "anomaly_metadata.json"

    result.to_csv(signals_path, index=False)
    counts.to_csv(summary_path, index=False)

    metadata["output_sha256"] = {
        str(signals_path): sha256(signals_path),
        str(summary_path): sha256(summary_path),
    }

    metadata_path.write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )

    print("ANOMALY CHART DATA GENERATED")
    print("Total signal rows:", len(result))
    print("\nDetector summary:")
    print(counts.to_string(index=False))

    print("\nGenerated files:")
    for path in (signals_path, summary_path, metadata_path):
        print(path)


if __name__ == "__main__":
    main()
