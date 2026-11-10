from fastapi.testclient import TestClient

from caregrid.api import app
from caregrid.data_access import DataRepository, DatasetUnavailable


client = TestClient(app)


def test_health_reports_available_curated_datasets():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "available"
    assert response.json()["datasets"]["disease_monthly"]["rows"] == 96


def test_overview_exposes_observed_coverage_without_forecasts():
    response = client.get("/api/overview")
    payload = response.json()

    assert response.status_code == 200
    assert payload["coverage"]["monthly_periods"] == 48
    assert payload["coverage"]["annual_district_records"] == 280
    assert payload["forecasting_available"] is False


def test_monthly_filter_preserves_source_classification_and_csv_fields():
    response = client.get(
        "/api/disease/monthly",
        params={"disease": "Dengue", "year": 2021},
    )

    assert response.status_code == 200
    records = response.json()["records"]
    assert len(records) == 12
    assert {row["classification"] for row in records} == {
        "reported_category_status_not_split"
    }


def test_impossible_disease_year_filter_is_rejected():
    assert client.get("/api/disease/monthly", params={"year": 2030}).status_code == 422


def test_valid_classification_with_no_matching_year_returns_empty_records():
    response = client.get(
        "/api/disease/monthly",
        params={"year": 2024, "classification": "reported_category_status_not_split"},
    )

    assert response.status_code == 200
    assert response.json()["records"] == []


def test_district_route_returns_annual_not_monthly_values():
    response = client.get(
        "/api/districts",
        params={"year": 2024, "disease": "Dengue", "classification": "Confirmed"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["temporal_granularity"] == "annual"
    assert len(payload["records"]) == 14
    assert all(row["year"] == 2024 for row in payload["records"])


def test_climate_response_labels_proxy_and_returns_observed_points():
    response = client.get(
        "/api/climate",
        params={"disease": "Dengue", "classification": "Confirmed"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert "proxy" in payload["weather_scope"].lower()
    assert len(payload["weather"]) == 48
    assert len(payload["disease_records"]) == 24


def test_methodology_contains_discrepancy_and_no_prediction_claim():
    payload = client.get("/api/methodology").json()

    assert payload["forecasting_available"] is False
    assert payload["district_boundary_data_available"] is False
    assert any("3,251" in caveat and "3,261" in caveat for caveat in payload["caveats"])


def test_methodology_report_link_is_served_and_unknown_files_are_blocked():
    response = client.get("/api/reports/analysis_data_readiness.md")

    assert response.status_code == 200
    assert "Analysis data readiness" in response.text
    live_report = client.get("/api/reports/live_kerala_surveillance_data_quality.md")
    assert live_report.status_code == 200
    assert "not live surveillance" in live_report.text
    assert client.get("/api/reports/requirements.txt").status_code == 404


def test_missing_required_data_returns_service_unavailable(monkeypatch):
    def fail_load(cls):
        raise DatasetUnavailable("Required project datasets are missing.")

    monkeypatch.setattr(DataRepository, "load", classmethod(fail_load))
    response = client.get("/api/overview")

    assert response.status_code == 503
    assert "datasets are missing" in response.json()["detail"]
