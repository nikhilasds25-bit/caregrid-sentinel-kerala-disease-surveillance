"""Strict loaders and feature construction for versioned candidate inputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from caregrid.multimodel.types import ModelReadiness

ROOT = Path(__file__).resolve().parents[3]
DISEASE_PATH = (
    ROOT / "data" / "candidates"
    / "kerala_district_monthly_disease_dashboard_2016_2025.csv"
)
DISEASE_METADATA_PATH = (
    ROOT / "data" / "candidates"
    / "kerala_district_monthly_disease_dashboard_2016_2025.metadata.json"
)
RECONCILIATION_PATH = (
    ROOT / "data" / "candidates"
    / "kerala_district_monthly_disease_dashboard_2016_2025_reconciliation.csv"
)
WEATHER_PATH = (
    ROOT / "data" / "candidates"
    / "kerala_district_representative_weather_monthly_2016_2025.csv"
)
WEATHER_METADATA_PATH = (
    ROOT / "data" / "candidates"
    / "kerala_district_representative_weather_monthly_2016_2025.metadata.json"
)
DISEASES = ("Dengue", "Leptospirosis")
WEATHER_FEATURES = (
    "precipitation_sum_mm",
    "temperature_2m_mean_c",
    "temperature_2m_min_c",
    "temperature_2m_max_c",
    "relative_humidity_2m_mean_pct",
    "dew_point_2m_mean_c",
)


class ModelDataError(ValueError):
    """Raised when source candidates or forecast features fail readiness checks."""


def _read_verified_candidate(
    data_path: Path,
    metadata_path: Path,
    hash_key: str,
) -> tuple[pd.DataFrame, dict[str, Any], str]:
    if not data_path.is_file() or not metadata_path.is_file():
        raise ModelDataError(
            f"Missing required candidate or metadata: {data_path}, {metadata_path}"
        )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    actual_hash = hashlib.sha256(data_path.read_bytes()).hexdigest()
    expected_hash = metadata.get(hash_key)
    if not expected_hash or actual_hash != expected_hash:
        raise ModelDataError(
            f"Candidate hash mismatch for {data_path}: expected={expected_hash}, "
            f"actual={actual_hash}"
        )
    return pd.read_csv(data_path), metadata, actual_hash


def load_model_ready_data(
    disease_path: Path = DISEASE_PATH,
    disease_metadata_path: Path = DISEASE_METADATA_PATH,
    reconciliation_path: Path = RECONCILIATION_PATH,
    weather_path: Path = WEATHER_PATH,
    weather_metadata_path: Path = WEATHER_METADATA_PATH,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    disease, disease_metadata, disease_hash = _read_verified_candidate(
        disease_path, disease_metadata_path, "candidate_sha256"
    )
    weather, weather_metadata, weather_hash = _read_verified_candidate(
        weather_path, weather_metadata_path, "candidate_csv_sha256"
    )
    if not reconciliation_path.is_file():
        raise ModelDataError(f"Missing reconciliation input: {reconciliation_path}")
    expected_reconciliation_hash = disease_metadata.get("reconciliation_sha256")
    reconciliation_hash = hashlib.sha256(reconciliation_path.read_bytes()).hexdigest()
    if reconciliation_hash != expected_reconciliation_hash:
        raise ModelDataError(
            "Reconciliation input hash does not match candidate metadata."
        )
    reconciliation = pd.read_csv(reconciliation_path)

    required = {
        "period", "year", "month_num", "district", "disease", "classification",
        "source_category_code", "cases", "deaths", "source_sha256",
        "availability_status", "cases_available",
    }
    if missing := sorted(required - set(disease.columns)):
        raise ModelDataError(f"Disease candidate is missing columns: {missing}")
    if disease["source_sha256"].nunique() != 1:
        raise ModelDataError("Disease candidate contains multiple source snapshot hashes.")
    if disease["source_sha256"].iloc[0] != disease_metadata.get("source_sha256"):
        raise ModelDataError("Disease rows are not bound to metadata's source snapshot.")
    if set(disease["classification"].dropna()) != {"Confirmed", "Suspected"}:
        raise ModelDataError("Disease candidate classification vocabulary changed.")
    if set(disease["disease"].dropna()) != set(DISEASES):
        raise ModelDataError("Disease candidate disease vocabulary changed.")
    if disease.duplicated(
        ["period", "district", "disease", "classification"]
    ).any():
        raise ModelDataError("Disease candidate contains duplicate natural keys.")

    confirmed = disease[
        disease["classification"].eq("Confirmed")
        & disease["disease"].isin(DISEASES)
    ].copy()
    if confirmed["cases"].isna().any() or not confirmed["cases_available"].all():
        raise ModelDataError("Confirmed target has unavailable case observations.")
    if (~np.isfinite(confirmed["cases"].to_numpy(dtype=float))).any():
        raise ModelDataError("Confirmed target contains non-finite cases.")
    if (confirmed["cases"] < 0).any() or (confirmed["cases"] % 1 != 0).any():
        raise ModelDataError("Confirmed target must contain non-negative integer counts.")
    expected_months = [f"{year}-{month:02d}" for year in range(2016, 2026) for month in range(1, 13)]
    if sorted(confirmed["period"].unique().tolist()) != expected_months:
        raise ModelDataError("Confirmed target does not cover every month from 2016 to 2025.")
    if confirmed.groupby("disease")["district"].nunique().to_dict() != {
        disease_name: 14 for disease_name in DISEASES
    }:
        raise ModelDataError("Each Confirmed disease must cover exactly 14 districts.")
    if not confirmed.groupby(["disease", "district"])["period"].nunique().eq(120).all():
        raise ModelDataError(
            "Every Confirmed disease-district series must contain all 120 months."
        )

    recon_columns = [
        "period", "source_category_code", "cases_reconciliation_status",
        "cases_difference",
    ]
    recon = reconciliation[recon_columns].rename(
        columns={
            "cases_reconciliation_status": "state_cases_reconciliation_status",
            "cases_difference": "state_case_sum_difference",
        }
    )
    confirmed = confirmed.merge(
        recon,
        on=["period", "source_category_code"],
        how="left",
        validate="many_to_one",
    )
    if confirmed["state_cases_reconciliation_status"].isna().any():
        raise ModelDataError("Confirmed candidate is missing state reconciliation flags.")
    reconciliation_mismatches = reconciliation[
        reconciliation["cases_reconciliation_status"].eq("mismatch")
    ]
    confirmed_reconciliation_mismatches = reconciliation_mismatches[
        reconciliation_mismatches["classification"].eq("Confirmed")
    ]

    if weather.duplicated(["period", "district"]).any():
        raise ModelDataError("Weather candidate contains duplicate district-month keys.")
    if not weather["weather_availability_status"].eq("complete_month").all():
        raise ModelDataError("Weather candidate contains incomplete monthly rows.")
    if weather[list(WEATHER_FEATURES)].isna().any().any():
        raise ModelDataError("Weather candidate has missing climate features.")
    if weather["period"].nunique() != 120 or weather["district"].nunique() != 14:
        raise ModelDataError("Weather candidate does not cover the expected 14x120 panel.")
    if len(weather) != 14 * 120 or not (
        weather.groupby("district")["period"].nunique().eq(120).all()
    ):
        raise ModelDataError("Weather candidate is missing district-month combinations.")

    confirmed = confirmed.merge(
        weather[["period", "district", *WEATHER_FEATURES]],
        on=["period", "district"],
        how="left",
        validate="many_to_one",
        indicator=True,
    )
    if not confirmed["_merge"].eq("both").all():
        raise ModelDataError("Confirmed disease records do not all have weather matches.")
    confirmed = confirmed.drop(columns="_merge")
    confirmed["period_start"] = pd.PeriodIndex(confirmed["period"], freq="M").to_timestamp()
    confirmed = confirmed.sort_values(
        ["disease", "district", "period_start"], kind="stable"
    ).reset_index(drop=True)

    confirmed["lag_cases"] = confirmed.groupby(
        ["disease", "district"], sort=False
    )["cases"].shift(1)
    confirmed["log_lag_cases"] = np.log1p(confirmed["lag_cases"])
    for column in WEATHER_FEATURES:
        confirmed[f"lag1_{column}"] = confirmed.groupby(
            ["disease", "district"], sort=False
        )[column].shift(1)
    confirmed["lag3_rainfall_sum_mm"] = (
        confirmed.groupby(["disease", "district"], sort=False)[
            "precipitation_sum_mm"
        ].transform(lambda values: values.shift(1).rolling(3, min_periods=3).sum())
    )
    confirmed["lag1_temperature_range_c"] = (
        confirmed["lag1_temperature_2m_max_c"]
        - confirmed["lag1_temperature_2m_min_c"]
    )
    confirmed["trend_years"] = (
        confirmed["period_start"].dt.year
        + (confirmed["period_start"].dt.month - 1) / 12
        - 2016
    )
    confirmed["month_num"] = confirmed["period_start"].dt.month

    provenance = {
        "disease_candidate_path": str(disease_path),
        "disease_candidate_sha256": disease_hash,
        "disease_source_sha256": disease_metadata["source_sha256"],
        "disease_metadata_path": str(disease_metadata_path),
        "disease_metadata_sha256": hashlib.sha256(
            disease_metadata_path.read_bytes()
        ).hexdigest(),
        "reconciliation_path": str(reconciliation_path),
        "reconciliation_sha256": reconciliation_hash,
        "weather_candidate_path": str(weather_path),
        "weather_candidate_sha256": weather_hash,
        "weather_metadata_path": str(weather_metadata_path),
        "weather_metadata_sha256": hashlib.sha256(
            weather_metadata_path.read_bytes()
        ).hexdigest(),
        "weather_source_batch_sha256": weather_metadata["batch_response_sha256"],
        "confirmed_rows": int(len(confirmed)),
        "district_count": int(confirmed["district"].nunique()),
        "period_count": int(confirmed["period"].nunique()),
        "confirmed_missing_cases": int(confirmed["cases"].isna().sum()),
        "confirmed_zero_cases": int(confirmed["cases"].eq(0).sum()),
        "reconciliation_flagged_confirmed_rows": int(
            confirmed["state_cases_reconciliation_status"].eq("mismatch").sum()
        ),
        "reconciliation_mismatch_cells": int(len(reconciliation_mismatches)),
        "confirmed_reconciliation_mismatch_cells": int(
            len(confirmed_reconciliation_mismatches)
        ),
        "weather_matched_rows": int(len(confirmed)),
        "classification_note": (
            "Dashboard Confirmed only; no mapping to DHS categories. "
            "Historical semantic consistency remains unverified."
        ),
        "climate_forecast_note": (
            "Climate features for each target month are constructed only from data "
            "available through the forecast origin."
        ),
    }
    readiness = {
        "confirmed_panel": {
            "status": "ready_for_exploratory_retrospective_comparison",
            "rows_per_disease": {
                name: int((confirmed["disease"] == name).sum()) for name in DISEASES
            },
            "months_per_district_disease": 120,
            "zero_cases": provenance["confirmed_zero_cases"],
            "missing_cases": provenance["confirmed_missing_cases"],
            "district_to_state_case_mismatch_rows": provenance[
                "reconciliation_flagged_confirmed_rows"
            ],
            "district_to_state_case_mismatch_cells": provenance[
                "confirmed_reconciliation_mismatch_cells"
            ],
            "all_classification_mismatch_cells": provenance[
                "reconciliation_mismatch_cells"
            ],
        },
        "climate_panel": {
            "status": "complete_historical_representative_location_panel",
            "matched_disease_rows": provenance["weather_matched_rows"],
            "features": list(WEATHER_FEATURES),
            "spatial_limitation": (
                "One API grid point per district representative location, not an "
                "areal district weather average."
            ),
            "forecast_origin_limitation": (
                "Forecast-time climate features are frozen at the latest observation "
                "available at each origin; realized future weather is not used."
            ),
        },
    }
    return confirmed, {"provenance": provenance, "readiness": readiness}
