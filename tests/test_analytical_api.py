"""Tests for versioned exploratory analytical API endpoints."""

import pytest
from fastapi.testclient import TestClient

from caregrid.api import app

client = TestClient(app)

ENDPOINTS = [
    "/api/v1/surveillance/observations",
    "/api/v1/forecasts",
    "/api/v1/model-comparisons",
    "/api/v1/detection/signals",
    "/api/v1/exceedance/assessments",
]


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_endpoints_use_approved_response_envelope(endpoint):
    response = client.get(endpoint)

    assert response.status_code == 200
    payload = response.json()

    assert isinstance(payload["data"], list)
    assert payload["meta"]["schema_version"] == "1.0"
    assert payload["meta"]["status"] == "exploratory"
    assert "generated_at" in payload["meta"]
    assert "filters" in payload["meta"]
    assert "limitations" in payload["meta"]


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/v1/forecasts",
        "/api/v1/model-comparisons",
        "/api/v1/detection/signals",
        "/api/v1/exceedance/assessments",
    ],
)
def test_analytical_endpoints_do_not_expose_actual_field(endpoint):
    response = client.get(endpoint)

    assert response.status_code == 200
    assert all("actual" not in row for row in response.json()["data"])


def test_forecasts_are_explicitly_historical_backtests():
    response = client.get(
        "/api/v1/forecasts",
        params={"disease": "Dengue", "district": "Ernakulam"},
    )

    assert response.status_code == 200

    records = response.json()["data"]
    assert records
    assert all(row["prediction_type"] == "backtest" for row in records)


def test_observations_preserve_source_classification():
    response = client.get(
        "/api/v1/surveillance/observations",
        params={"disease": "Dengue", "year": 2021},
    )

    assert response.status_code == 200

    records = response.json()["data"]
    assert len(records) == 12
    assert {row["classification"] for row in records} == {
        "reported_category_status_not_split"
    }
    assert all(row["observation_type"] == "reported_observation" for row in records)


def test_monthly_district_observations_are_rejected():
    response = client.get(
        "/api/v1/surveillance/observations",
        params={"granularity": "monthly", "district": "Ernakulam"},
    )

    assert response.status_code == 422


def test_annual_district_observations_remain_annual():
    response = client.get(
        "/api/v1/surveillance/observations",
        params={
            "granularity": "annual",
            "district": "Ernakulam",
            "disease": "Dengue",
            "year": 2024,
        },
    )

    assert response.status_code == 200

    records = response.json()["data"]
    assert records
    assert all(row["temporal_granularity"] == "annual" for row in records)
    assert all(row["district"] == "Ernakulam" for row in records)


def test_invalid_granularity_returns_422():
    response = client.get(
        "/api/v1/surveillance/observations",
        params={"granularity": "weekly"},
    )

    assert response.status_code == 422


def test_invalid_disease_filter_returns_422():
    response = client.get(
        "/api/v1/forecasts",
        params={"disease": "NonexistentDisease"},
    )

    assert response.status_code == 422


def test_exceedance_preserves_unavailable_probabilities():
    response = client.get("/api/v1/exceedance/assessments")

    assert response.status_code == 200

    records = response.json()["data"]
    assert records
    assert any(row["predicted_probability"] is None for row in records)
    assert all(
        row["calibration_status"] is not None
        for row in records
    )


def test_detection_signals_remain_exploratory():
    response = client.get("/api/v1/detection/signals")

    assert response.status_code == 200

    records = response.json()["data"]
    assert records
    assert all("unusual_activity_flag" in row for row in records)
    assert all("evidence_role" in row for row in records)


def test_district_dashboard_returns_confirmed_monthly_observations():
    response = client.get(
        "/api/v1/surveillance/observations",
        params={
            "source": "district_dashboard",
            "disease": "Dengue",
            "district": "Ernakulam",
            "granularity": "monthly",
            "classification": "Confirmed",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    records = payload["data"]

    assert len(records) == 120
    assert payload["meta"]["geographic_granularity"] == "district"
    assert payload["meta"]["source_dataset"].endswith(
        "kerala_district_monthly_disease_dashboard_2016_2025.csv"
    )
    assert all(row["disease"] == "Dengue" for row in records)
    assert all(row["district"] == "Ernakulam" for row in records)
    assert all(row["classification"] == "Confirmed" for row in records)
    assert all(row["temporal_granularity"] == "monthly" for row in records)
    assert all(row["observation_type"] == "reported_observation" for row in records)


def test_curated_monthly_district_restriction_is_preserved():
    response = client.get(
        "/api/v1/surveillance/observations",
        params={
            "source": "curated",
            "district": "Ernakulam",
            "granularity": "monthly",
        },
    )
    assert response.status_code == 422


def test_district_dashboard_rejects_annual_granularity():
    response = client.get(
        "/api/v1/surveillance/observations",
        params={
            "source": "district_dashboard",
            "granularity": "annual",
        },
    )
    assert response.status_code == 422


def test_district_dashboard_preserves_empty_results():
    response = client.get(
        "/api/v1/surveillance/observations",
        params={
            "source": "district_dashboard",
            "disease": "Dengue",
            "district": "Ernakulam",
            "classification": "Probable",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"] == []
