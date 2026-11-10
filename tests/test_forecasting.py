from __future__ import annotations

import json
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from caregrid import forecasting
from caregrid.api import app
from caregrid.data_access import DataRepository


ROOT = forecasting.ROOT
client = TestClient(app)


def test_naive_forecast_repeats_only_last_training_value():
    assert forecasting.naive_forecast([2, 0, 7], 3) == [7.0, 7.0, 7.0]


def test_seasonal_naive_forecast_repeats_latest_observed_year():
    assert forecasting.seasonal_naive_forecast(list(range(1, 13)), 14) == [
        *[float(value) for value in range(1, 13)],
        1.0,
        2.0,
    ]


def test_forecast_functions_reject_insufficient_or_invalid_inputs():
    with pytest.raises(forecasting.ForecastExperimentError, match="at least one observation"):
        forecasting.naive_forecast([], 1)
    with pytest.raises(forecasting.ForecastExperimentError, match="at least 12"):
        forecasting.seasonal_naive_forecast([1, 2, 3], 1)
    with pytest.raises(forecasting.ForecastExperimentError, match="missing values"):
        forecasting.naive_forecast([1, np.nan], 1)
    with pytest.raises(forecasting.ForecastExperimentError, match="at least one"):
        forecasting.naive_forecast([1], 0)


def test_readiness_audit_counts_actual_series_coverage_and_keeps_classes_separate():
    audit = forecasting.build_readiness_audit(DataRepository.load(ROOT), ROOT)

    lookup = {
        (row["disease"], row["classification"]): row
        for row in audit["series"]
    }
    assert lookup[("Dengue", "reported_category_status_not_split")]["valid_observations"] == 12
    assert lookup[("Dengue", "non_probable_category_probable_separate")]["valid_observations"] == 12
    assert lookup[("Dengue", "Confirmed")]["valid_observations"] == 24
    assert lookup[("Leptospirosis", "Confirmed")]["valid_observations"] == 24
    assert lookup[("Dengue", "Confirmed")]["missing_months"] == []
    assert lookup[("Dengue", "Confirmed")]["duplicate_months"] == []
    assert audit["evaluation"]["proposed_2021_2023_train_2024_test_feasible"] is False
    assert audit["annual_district_dataset_used"] is False
    assert audit["2025_annual_surveillance_used"] is False
    assert audit["idsp_daily_used"] is False
    assert audit["climate"]["matched_confirmed_disease_months"] == 24
    assert audit["evaluation"]["confirmed_2023_train_2024_test"]["Dengue"][
        "eligible_for_limited_2024_holdout"
    ]


def test_series_readiness_reports_missing_duplicate_months_zeroes_and_source_changes():
    frame = pd.DataFrame({
        "period": ["2024-01", "2024-03", "2024-03"],
        "cases": [0, 4, 4],
        "classification": ["Confirmed"] * 3,
        "classification_note": ["explicit"] * 3,
        "source_file": ["a.pdf", "b.pdf", "b.pdf"],
    })

    readiness = forecasting.series_readiness(frame)

    assert readiness["valid_observations"] == 3
    assert readiness["missing_months"] == ["2024-02"]
    assert readiness["duplicate_months"] == ["2024-03"]
    assert readiness["zero_observations"] == 1
    assert readiness["source_change"] is True


def test_chronological_split_rejects_duplicate_months_and_prevents_future_leakage():
    frame = pd.DataFrame({
        "period": ["2023-01", "2023-02", "2024-01", "2024-02"],
        "cases": [1, 2, 3, 4],
    })
    train, test = forecasting.chronological_split(
        frame,
        train_end="2023-12",
        test_start="2024-01",
        test_end="2024-02",
    )
    changed_future = frame.copy()
    changed_future.loc[2:, "cases"] = [300, 400]
    changed_train, _ = forecasting.chronological_split(
        changed_future,
        train_end="2023-12",
        test_start="2024-01",
        test_end="2024-02",
    )

    assert train["cases"].tolist() == changed_train["cases"].tolist() == [1, 2]
    assert test["period"].tolist() == ["2024-01", "2024-02"]
    assert forecasting.naive_forecast(train["cases"].tolist(), len(test)) == [2.0, 2.0]
    duplicate = pd.concat([frame, frame.iloc[[0]]], ignore_index=True).sort_values("period")
    with pytest.raises(forecasting.ForecastExperimentError, match="duplicate"):
        forecasting.chronological_split(
            duplicate,
            train_end="2023-12",
            test_start="2024-01",
            test_end="2024-02",
        )


def test_metrics_handle_zero_denominators_and_training_only_seasonal_scale():
    metrics = forecasting.calculate_metrics(
        actual=[0, 2],
        predicted=[1, 1],
        training_values=[0] * 12,
    )
    assert metrics == {"mae": 1.0, "rmse": 1.0, "mase": None}

    scaled = forecasting.calculate_metrics(
        actual=[4, 8],
        predicted=[2, 10],
        training_values=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 3, 6],
    )
    assert scaled["mae"] == 2.0
    assert scaled["rmse"] == 2.0
    assert scaled["mase"] == pytest.approx(2 / 3)


def test_climate_features_align_by_unique_month_without_filling_gaps():
    disease = pd.DataFrame({"period": ["2023-01", "2023-02"], "cases": [1, 2]})
    weather = pd.DataFrame({
        "period": ["2023-01", "2023-02"],
        "precipitation_sum_mm": [5.0, 8.0],
        "temperature_2m_mean_c": [27.0, 28.0],
        "temperature_2m_min_c": [24.0, 25.0],
        "temperature_2m_max_c": [30.0, 31.0],
    })
    aligned = forecasting.align_climate_features(disease, weather)
    assert aligned["precipitation_sum_mm"].tolist() == [5.0, 8.0]

    with pytest.raises(forecasting.ForecastExperimentError, match="does not cover"):
        forecasting.align_climate_features(disease, weather.iloc[[0]])
    with pytest.raises(forecasting.ForecastExperimentError, match="duplicate"):
        forecasting.align_climate_features(
            disease,
            pd.concat([weather, weather.iloc[[0]]], ignore_index=True),
        )


def test_api_serves_experiment_and_returns_explicit_unavailable_on_stale_artifact(monkeypatch):
    sample = {
        "status": "experimental_baseline_hindcast",
        "validity_checks_passed": True,
        "future_forecasts_available": False,
        "evaluation_metrics": [],
        "actual_vs_predicted": [],
    }
    monkeypatch.setattr("caregrid.api.load_experiment_artifact", lambda: sample)
    response = client.get("/api/forecasting/experiment")
    assert response.status_code == 200
    assert response.json()["future_forecasts_available"] is False

    def stale():
        raise forecasting.ForecastExperimentError("rerun the experiment")

    monkeypatch.setattr("caregrid.api.load_experiment_artifact", stale)
    unavailable = client.get("/api/forecasting/experiment")
    assert unavailable.status_code == 503
    assert "rerun" in unavailable.json()["detail"]


def test_experiment_artifact_is_bound_to_disease_and_weather_inputs(tmp_path):
    experiment_dir = tmp_path / forecasting.EXPERIMENT_DIR
    experiment_dir.mkdir(parents=True)
    disease_path = tmp_path / "data/processed/kerala_disease_monthly_2021_2024.csv"
    weather_path = tmp_path / "data/processed/kerala_weather_monthly_district_proxy_2021_2024.csv"
    disease_path.parent.mkdir(parents=True)
    disease_path.write_bytes(b"historical disease input")
    weather_path.write_bytes(b"historical weather input")
    artifact = {
        "source_sha256": forecasting.hashlib.sha256(disease_path.read_bytes()).hexdigest(),
        "weather_source_sha256": forecasting.hashlib.sha256(weather_path.read_bytes()).hexdigest(),
    }
    (experiment_dir / "experiment.json").write_text(json.dumps(artifact), encoding="utf-8")

    assert forecasting.load_experiment_artifact(tmp_path) == artifact
    weather_path.write_bytes(b"changed weather")
    with pytest.raises(forecasting.ForecastExperimentError, match="do not match"):
        forecasting.load_experiment_artifact(tmp_path)
