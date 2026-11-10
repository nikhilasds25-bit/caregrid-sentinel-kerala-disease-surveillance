from __future__ import annotations

import copy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from caregrid import import_official_surveillance_report as importer
from caregrid import surveillance
from caregrid.api import app


ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "data" / "raw" / "DHS-CD-Data-2025-Approved.pdf"
client = TestClient(app)


@pytest.fixture(scope="module")
def report_bytes() -> bytes:
    return PDF_PATH.read_bytes()


@pytest.fixture(scope="module")
def valid_snapshot(report_bytes: bytes) -> dict:
    return importer.parse_official_pdf(
        report_bytes,
        retrieved_at_utc="2026-11-02T10:40:00+00:00",
        last_modified="Wed, 23 Sep 2026 13:51:49 GMT",
    )


def test_official_report_parse_validates_monthly_totals_and_preserves_groups(valid_snapshot):
    snapshot = valid_snapshot

    assert snapshot["reporting_period_start"] == "2025-01"
    assert snapshot["reporting_period_end"] == "2025-12"
    assert len(snapshot["monthly_records"]) == 324
    assert len(snapshot["monthly_validation_totals"]) == 27
    assert all(
        row["monthly_cases_sum_matches_annual"] and row["monthly_deaths_sum_matches_annual"]
        for row in snapshot["monthly_validation_totals"]
    )
    dengue_groups = {
        row["classification"] for row in snapshot["monthly_records"]
        if row["disease"] == "Dengue"
    }
    assert dengue_groups == {"Confirmed", "Probable"}
    assert {
        (row["classification"], row["source_label"])
        for row in snapshot["monthly_records"]
        if row["disease"] == "Rabies"
    } == {("Confirmed", "Con Rabies"), ("Suspected", "Sus Rabies")}
    assert snapshot["missing_districts"] == ["Alappuzha"]
    assert len(snapshot["reported_districts"]) == 13
    assert snapshot["source_sha256"] == importer.sha256_bytes(PDF_PATH.read_bytes())


def test_official_report_contains_expected_district_mapping(valid_snapshot):
    assert set(valid_snapshot["reported_districts"]) == set(surveillance.EXPECTED_DISTRICTS) - {
        "Alappuzha"
    }
    district_rows = valid_snapshot["district_annual_records"]
    assert all(row["year"] == 2025 for row in district_rows)
    assert all("district" in row and row["district"] != "Alappuzha" for row in district_rows)


def test_malformed_pdf_and_table_counts_are_rejected():
    with pytest.raises(importer.ReportImportError, match="PDF signature"):
        importer.parse_official_pdf(b"<html>not an official report</html>")
    with pytest.raises(importer.ReportImportError, match="Invalid or missing case count"):
        importer._table_count("unknown", "case count")


def test_snapshot_validation_rejects_duplicate_records(valid_snapshot):
    invalid = copy.deepcopy(valid_snapshot)
    invalid["monthly_records"].append(copy.deepcopy(invalid["monthly_records"][0]))

    with pytest.raises(surveillance.SurveillanceUnavailable, match="duplicate natural keys"):
        surveillance.validate_snapshot(invalid)


def test_suspicious_death_count_is_flagged_and_retained(valid_snapshot):
    flagged = copy.deepcopy(valid_snapshot)
    record = flagged["monthly_records"][0]
    record["cases"] = 0
    record["deaths"] = 1
    flagged["suspicious_value_flags"] = surveillance.find_suspicious_value_flags(flagged)
    flagged["validation_status"] = "passed_with_quality_flags"

    surveillance.validate_snapshot(flagged)

    assert flagged["suspicious_value_flags"][0]["reason"].startswith(
        "Reported deaths exceed reported cases"
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda snapshot: snapshot["monthly_records"][0].update(cases=None), "missing required values"),
        (lambda snapshot: snapshot["monthly_records"][0].update(deaths=-1), "negative"),
        (lambda snapshot: snapshot["monthly_records"][0].update(period="2025-13"), "invalid reporting period"),
        (lambda snapshot: snapshot["monthly_records"][0].update(period="2025-02"), "duplicate natural keys"),
        (lambda snapshot: snapshot["district_annual_records"][0].update(district="Unknown"), "Unknown official district"),
    ],
)
def test_snapshot_validation_rejects_missing_invalid_or_unmapped_values(
    valid_snapshot, mutation, message
):
    invalid = copy.deepcopy(valid_snapshot)
    mutation(invalid)

    with pytest.raises(surveillance.SurveillanceUnavailable, match=message):
        surveillance.validate_snapshot(invalid)


class FakeResponse:
    url = importer.SOURCE_PDF_URL
    headers = {
        "Content-Type": "application/pdf",
        "Date": "Mon, 02 Nov 2026 10:40:00 GMT",
        "Last-Modified": "Wed, 23 Sep 2026 13:51:49 GMT",
    }

    def __init__(self, content: bytes):
        self.content = content
        self.status_checked = False

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return None

    def raise_for_status(self):
        self.status_checked = True

    def iter_content(self, chunk_size: int):
        assert chunk_size == 64 * 1024
        for index in range(0, len(self.content), chunk_size):
            yield self.content[index:index + chunk_size]


class FakeSession:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.request_args = None

    def get(self, url: str, **kwargs):
        self.request_args = (url, kwargs)
        return self.response


def test_verified_source_retrieval_uses_exact_url_timeout_and_pdf_signature(report_bytes):
    response = FakeResponse(report_bytes)
    session = FakeSession(response)

    content, modified, retrieved, server_date = importer.fetch_official_pdf(session)

    assert content == report_bytes
    assert modified == response.headers["Last-Modified"]
    assert retrieved.endswith("+00:00")
    assert server_date == response.headers["Date"]
    assert session.request_args[0] == importer.SOURCE_PDF_URL
    assert session.request_args[1]["timeout"] == (10, 30)
    assert session.request_args[1]["allow_redirects"] is True
    assert response.status_checked


def test_source_response_with_unexpected_content_type_is_rejected(report_bytes):
    response = FakeResponse(report_bytes)
    response.headers["Content-Type"] = "text/html"

    with pytest.raises(importer.ReportImportError, match="non-PDF content type"):
        importer.fetch_official_pdf(FakeSession(response))


def test_failed_refresh_retains_last_successful_cached_snapshot(
    valid_snapshot, monkeypatch, tmp_path
):
    latest_path = tmp_path / "latest.json"
    status_path = tmp_path / "source_status.json"
    monkeypatch.setattr(surveillance, "LIVE_DIR", tmp_path)
    monkeypatch.setattr(surveillance, "SNAPSHOT_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(surveillance, "LATEST_PATH", latest_path)
    monkeypatch.setattr(surveillance, "STATUS_PATH", status_path)
    monkeypatch.setattr(surveillance, "ROOT", tmp_path)
    surveillance.record_refresh_success(valid_snapshot)
    prior_snapshot = latest_path.read_bytes()

    monkeypatch.setattr(
        importer,
        "fetch_official_pdf",
        lambda: (_ for _ in ()).throw(importer.ReportImportError("DHS source timed out.")),
    )
    with pytest.raises(importer.ReportImportError, match="timed out"):
        importer.import_report(download=True)

    assert latest_path.read_bytes() == prior_snapshot
    assert surveillance.load_snapshot()["source_sha256"] == valid_snapshot["source_sha256"]
    assert surveillance.get_source_status()["status"] == "source_unavailable"
    assert surveillance.get_source_status()["last_attempt"]["cached_snapshot_retained"] is True


def test_live_api_separates_2025_snapshot_from_historical_api():
    summary = client.get("/api/live-surveillance/summary")
    history = client.get("/api/overview")

    assert summary.status_code == 200
    assert summary.json()["reporting_period_end"] == "2025-12"
    assert summary.json()["is_live"] is False
    assert summary.json()["current_2026_information_available"] is False
    assert history.status_code == 200
    assert history.json()["coverage"]["monthly_period_end"] == "2024-12"


def test_live_api_disease_district_trend_and_status_responses():
    disease = client.get(
        "/api/live-surveillance/diseases",
        params={"disease": "Dengue", "classification": "Confirmed"},
    ).json()
    districts = client.get(
        "/api/live-surveillance/districts",
        params={"disease": "Dengue", "classification": "Confirmed"},
    ).json()
    trends = client.get(
        "/api/live-surveillance/trends",
        params={"disease": "Dengue", "classification": "Confirmed"},
    ).json()
    status = client.get("/api/live-surveillance/source-status").json()
    update = client.get("/api/live-surveillance/last-update").json()

    assert disease["records"][0]["latest_period"] == "2025-12"
    assert disease["records"][0]["cases"] == 633
    assert districts["temporal_granularity"] == "annual district records, not district-month"
    assert len(districts["records"]) == 13
    assert districts["missing_districts"] == ["Alappuzha"]
    assert "not a risk classification" in districts["comparison_note"]
    assert len(trends["records"]) == 12
    assert status["snapshot_available"] is True
    assert status["publication_date"] is None
    assert update["last_successful_retrieval"] == status["last_successful_retrieval"]


def test_live_api_rejects_unknown_filter_and_keeps_source_endpoint_available():
    assert client.get(
        "/api/live-surveillance/trends", params={"disease": "Invented Disease"}
    ).status_code == 422
    source = client.get("/api/live-surveillance/source")
    assert source.status_code == 200
    assert source.json()["validation_status"] == "passed"


def test_summary_endpoint_reports_unavailable_without_historical_substitution(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(surveillance, "LATEST_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(surveillance, "STATUS_PATH", tmp_path / "missing_status.json")

    response = client.get("/api/live-surveillance/summary")
    payload = response.json()

    assert response.status_code == 200
    assert payload["data_status"] == "data_not_available"
    assert payload["current_2026_information_available"] is False
    assert payload["disease_statistics"] == []
    assert payload["source_status"]["snapshot_available"] is False


def test_freshness_thresholds_follow_annual_reporting_period():
    from datetime import date

    assert surveillance.get_source_status(date(2026, 3, 31))["status"] == "verified_recent"
    assert surveillance.get_source_status(date(2026, 4, 1))["status"] == "official_delayed"
    assert surveillance.get_source_status(date(2028, 1, 1))["status"] == "historical"
