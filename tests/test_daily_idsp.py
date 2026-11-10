from __future__ import annotations

import copy
import io
from datetime import date, datetime, timezone
from pathlib import Path

import pdfplumber
import pytest
import requests
from fastapi.testclient import TestClient

from caregrid import daily_surveillance as daily
from caregrid import import_idsp_daily as importer
from caregrid.api import app


ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "data" / "raw" / "idsp_daily" / "DR-CD-01.11.2026sd.pdf"
client = TestClient(app)
REPORT_POST_URL = "https://dhs.kerala.gov.in/en/2026/11/02/01-11-2026/"
REPORT_PDF_URL = (
    "https://dhs.kerala.gov.in/wp-content/uploads/2026/11/DR-CD-01.11.2026sd.pdf"
)


def freshness_status_for_age(age_days: int) -> str:
    if age_days <= 2:
        return "verified_recent"
    if age_days <= 7:
        return "official_delayed"
    return "historical"


@pytest.fixture(scope="module")
def report_bytes() -> bytes:
    return PDF_PATH.read_bytes()


@pytest.fixture(scope="module")
def daily_snapshot(report_bytes: bytes) -> dict:
    return importer.parse_daily_pdf(
        report_bytes,
        report_date=date(2026, 11, 1),
        source_page_url=REPORT_POST_URL,
        source_url=REPORT_PDF_URL,
        retrieved_at_utc="2026-11-02T12:00:00+00:00",
        source_response_date="Mon, 02 Nov 2026 11:55:16 GMT",
        source_last_modified="Mon, 02 Nov 2026 05:14:47 GMT",
        original_filename=PDF_PATH.name,
    )


def test_official_index_discovery_deduplicates_and_sorts_report_dates():
    html = """
      <a href="/en/2026/11/02/01-11-2026/">01/11/2026</a>
      <a href="/en/2026/11/02/01-11-2026/">01/11/2026</a>
      <a href="https://example.com/02-11-2026/">02/11/2026</a>
      <a href="/en/2026/10/31/31-10-2026/">31/10/2026</a>
    """
    found = importer.discover_reports(html)

    assert [row["report_date"] for row in found] == ["2026-11-01", "2026-10-31"]
    assert found[0]["post_url"] == REPORT_POST_URL


def test_official_post_publication_timestamp_is_extracted_from_published_time_element():
    html = (
        '<time class="entry-date published updated" '
        'datetime="2026-11-02T05:15:09+00:00"></time>'
    )
    assert importer.extract_post_published_at(html) == "2026-11-02T05:15:09+00:00"
    assert importer.extract_post_published_at("<html><body>No publication metadata</body></html>") is None


def test_pdf_parser_preserves_daily_month_to_date_cumulative_and_district_values(
    daily_snapshot,
):
    dengue = next(row for row in daily_snapshot["statewide_records"] if row["disease"] == "Dengue")
    lepto = next(
        row for row in daily_snapshot["statewide_records"]
        if row["disease"] == "Leptospirosis"
    )

    assert daily_snapshot["report_date"] == "2026-11-01"
    assert len(daily_snapshot["statewide_records"]) == 26
    assert len(daily_snapshot["reported_district_codes"]) == 14
    assert len(daily_snapshot["district_records"]) == 294
    assert dengue["daily"] == {
        "suspected_cases": 105,
        "suspected_deaths": None,
        "confirmed_cases": 80,
        "confirmed_deaths": None,
    }
    assert dengue["source_values"]["daily"]["suspected_deaths"] == "-"
    assert dengue["source_value_status"]["daily"]["suspected_deaths"] == "source_dash_uninterpreted"
    assert dengue["cumulative_2026"] == {
        "suspected_cases": 35419,
        "suspected_deaths": 35,
        "confirmed_cases": 13244,
        "confirmed_deaths": 44,
    }
    assert lepto["cumulative_2026"] == {
        "suspected_cases": 1455,
        "suspected_deaths": 92,
        "confirmed_cases": 2465,
        "confirmed_deaths": 123,
    }
    assert all(row["reconciles"] is None for row in daily_snapshot["district_reconciliation"])
    assert all(row["district_sum"] is None for row in daily_snapshot["district_reconciliation"])


def test_count_parser_preserves_missing_cells_and_treats_printed_dash_separately():
    assert importer._parse_count("", "source cases") == (None, "")
    assert importer._parse_count("-", "source deaths") == (None, "-")
    assert importer._parse_count("0", "source deaths") == (0, "0")
    assert importer._source_value_status("-") == "source_dash_uninterpreted"
    assert importer._source_value_status("") == "not_reported"
    assert importer._source_value_status("0") == "reported"
    with pytest.raises(importer.ReportImportError, match="Invalid source cases"):
        importer._parse_count("not reported", "source cases")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("01-11-26", date(2026, 11, 1)),
        ("30-10-2026", date(2026, 10, 30)),
        ("10/10/2026", date(2026, 10, 10)),
        ("26/07/26", date(2026, 7, 26)),
    ],
)
def test_table_report_date_accepts_observed_dhs_formats(raw, expected):
    assert importer._parse_table_report_date(raw) == expected


def test_earlier_district_table_format_preserves_all_14_districts():
    earlier_report = ROOT / "data" / "raw" / "idsp_daily" / "IDSP-Daily-Report-01.08.2026.pdf"
    with pdfplumber.open(earlier_report) as pdf:
        district_table = pdf.pages[1].extract_tables()[0]

    records, _reconciliation = importer._parse_district_table(
        district_table,
        date(2026, 8, 1),
    )

    assert len({row["district_code"] for row in records}) == 14
    assert len(records) > 0


def test_downloaded_but_unparseable_pdf_is_preserved_with_hash(monkeypatch, tmp_path):
    class FakeResponse:
        encoding = "utf-8"

        def __init__(self, url, body, content_type):
            self.url = url
            self.body = body
            self.headers = {"Content-Type": content_type}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size):
            yield self.body

    class FakeSession:
        def get(self, url, **_kwargs):
            if url == REPORT_POST_URL:
                body = f'<a href="{REPORT_PDF_URL}">PDF</a>'.encode()
                return FakeResponse(url, body, "text/html")
            return FakeResponse(url, b"%PDF-invalid", "application/pdf")

    monkeypatch.setattr(importer, "ROOT", tmp_path)
    with pytest.raises(importer.ReportImportError) as raised:
        importer.retrieve_candidate_report(
            FakeSession(),
            {"report_date": "2026-11-01", "post_url": REPORT_POST_URL},
        )

    failure = raised.value
    assert failure.source_url == REPORT_PDF_URL
    assert failure.source_sha256 == importer.sha256_bytes(b"%PDF-invalid")
    preserved = tmp_path / failure.original_file
    assert preserved.read_bytes() == b"%PDF-invalid"
    assert failure.retrieved_at_utc


def test_missing_district_cell_is_not_treated_as_zero_in_reconciliation(report_bytes):
    with importer.pdfplumber.open(io.BytesIO(report_bytes)) as pdf:
        district_table = pdf.pages[1].extract_tables()[0]
    district_table[5][7] = ""

    _records, reconciliation = importer._parse_district_table(
        district_table,
        date(2026, 11, 1),
    )
    dengue_suspected = next(
        row for row in reconciliation
        if row["disease"] == "Dengue" and row["classification"] == "Suspected"
    )

    assert dengue_suspected["district_sum"] is None
    assert dengue_suspected["difference"] is None
    assert dengue_suspected["reconciles"] is None


def test_statewide_reporting_period_must_match_pdf_header(report_bytes):
    with importer.pdfplumber.open(io.BytesIO(report_bytes)) as pdf:
        statewide_table = pdf.pages[2].extract_tables()[0]

    with pytest.raises(importer.ReportImportError, match="does not match discovered post date"):
        importer._parse_statewide_table(statewide_table, date(2026, 11, 2))


def test_successful_discovery_download_and_failed_refresh_retain_cached_snapshot(
    report_bytes, monkeypatch, tmp_path
):
    class FakeResponse:
        headers = {
            "Content-Type": "application/pdf",
            "Date": "Mon, 02 Nov 2026 11:55:16 GMT",
            "Last-Modified": "Mon, 02 Nov 2026 05:14:47 GMT",
        }
        encoding = "utf-8"

        def __init__(self, url: str, body: bytes, headers: dict | None = None):
            self.url = url
            self.body = body
            self.headers = headers or self.headers

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return None

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size: int):
            for offset in range(0, len(self.body), chunk_size):
                yield self.body[offset:offset + chunk_size]

    index = f'<a href="{REPORT_POST_URL}">01/11/2026</a>'.encode()
    post = f'<a href="{REPORT_PDF_URL}">Daily report PDF</a>'.encode()

    class SuccessfulSession:
        def get(self, url: str, **kwargs):
            assert kwargs["allow_redirects"] is True
            assert kwargs["timeout"][0] > 0
            if url == importer.INDEX_URL:
                return FakeResponse(url, index, {"Content-Type": "text/html"})
            if url == REPORT_POST_URL:
                return FakeResponse(url, post, {"Content-Type": "text/html"})
            if url == REPORT_PDF_URL:
                return FakeResponse(url, report_bytes)
            raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(importer, "ROOT", tmp_path)
    monkeypatch.setattr(daily, "ROOT", tmp_path)
    monkeypatch.setattr(daily, "DAILY_DIR", tmp_path / "data" / "live_surveillance" / "daily_idsp")
    monkeypatch.setattr(daily, "SNAPSHOT_DIR", daily.DAILY_DIR / "snapshots")
    monkeypatch.setattr(daily, "LATEST_PATH", daily.DAILY_DIR / "latest.json")
    monkeypatch.setattr(daily, "STATUS_PATH", daily.DAILY_DIR / "source_status.json")

    retrieved = importer.retrieve_latest_report(session=SuccessfulSession())
    preserved = daily.LATEST_PATH.read_bytes()

    assert retrieved["report_date"] == "2026-11-01"
    assert (tmp_path / "data" / "raw" / "idsp_daily" / PDF_PATH.name).read_bytes() == report_bytes
    assert retrieved["original_file"] == "data/raw/idsp_daily/DR-CD-01.11.2026sd.pdf"

    class UnavailableSession:
        def get(self, url: str, **kwargs):
            raise requests.Timeout("DHS timed out")

    with pytest.raises(importer.ReportImportError, match="Could not retrieve official DHS page"):
        importer.retrieve_latest_report(session=UnavailableSession())

    assert daily.LATEST_PATH.read_bytes() == preserved
    assert daily.get_daily_source_status(as_of=date(2026, 11, 2))["status"] == "source_unavailable"


def test_invalid_pdf_and_report_date_are_rejected():
    with pytest.raises(importer.ReportImportError, match="PDF signature"):
        importer.parse_daily_pdf(
            b"<html>not a PDF</html>",
            report_date=date(2026, 11, 1),
            source_page_url=REPORT_POST_URL,
            source_url=REPORT_PDF_URL,
            retrieved_at_utc="2026-11-02T12:00:00+00:00",
            source_response_date=None,
            source_last_modified=None,
            original_filename=PDF_PATH.name,
        )


def test_duplicate_report_date_links_are_not_imported_twice():
    links = (
        f'<a href="{REPORT_POST_URL}">01/11/2026</a>'
        f'<a href="{REPORT_POST_URL}?ref=duplicate">01/11/2026</a>'
    )
    assert len(importer.discover_reports(links)) == 1


def test_district_table_failure_keeps_statewide_snapshot_and_marks_district_unavailable(
    report_bytes, monkeypatch
):
    def reject_district_table(*args, **kwargs):
        raise importer.ReportImportError("District table layout is unrecognized.")

    monkeypatch.setattr(importer, "_parse_district_table", reject_district_table)
    snapshot = importer.parse_daily_pdf(
        report_bytes,
        report_date=date(2026, 11, 1),
        source_page_url=REPORT_POST_URL,
        source_url=REPORT_PDF_URL,
        retrieved_at_utc="2026-11-02T12:00:00+00:00",
        source_response_date=None,
        source_last_modified=None,
        original_filename=PDF_PATH.name,
    )

    assert snapshot["daily_district_report_available"] is False
    assert snapshot["district_records"] == []
    assert snapshot["district_report_error"] == "District table layout is unrecognized."
    assert len(snapshot["statewide_records"]) == 26


def test_missing_district_rows_are_reported_without_substituting_annual_values(report_bytes):
    with importer.pdfplumber.open(io.BytesIO(report_bytes)) as pdf:
        district_table = pdf.pages[1].extract_tables()[0]
    district_table[5] = [None] * 32

    rows, _reconciliation = importer._parse_district_table(
        district_table,
        date(2026, 11, 1),
    )
    reported_codes = {row["district_code"] for row in rows}

    assert len(reported_codes) == 13
    assert "TVM" not in reported_codes
    assert reported_codes == set(daily.EXPECTED_DISTRICT_CODES) - {"TVM"}


def test_snapshot_validation_detects_duplicate_disease_rows_and_invalid_dates(
    daily_snapshot,
):
    duplicate = copy.deepcopy(daily_snapshot)
    duplicate["statewide_records"].append(
        copy.deepcopy(duplicate["statewide_records"][0])
    )
    duplicate["quality_flags"] = daily.find_daily_quality_flags(duplicate)

    with pytest.raises(daily.DailySurveillanceUnavailable, match="duplicate natural keys"):
        daily.validate_daily_snapshot(duplicate)

    invalid_date = copy.deepcopy(daily_snapshot)
    invalid_date["report_date"] = "not-a-date"
    with pytest.raises(daily.DailySurveillanceUnavailable, match="report date"):
        daily.validate_daily_snapshot(invalid_date)


def test_district_codes_are_official_and_source_deaths_remain_unclassified(
    daily_snapshot,
):
    assert set(daily_snapshot["reported_district_codes"]) == set(daily.EXPECTED_DISTRICT_CODES)
    district_rows = daily.district_daily_statistics("Dengue")["records"]
    assert len(district_rows) == 14
    assert all(row["reported_deaths"] is None for row in district_rows)
    assert all(
        row["field_source_status"]["reported_deaths"] == "source_dash_uninterpreted"
        for row in district_rows
    )
    assert all(row["suspected_deaths"] is None for row in district_rows)
    assert "not assigned to a case classification" in daily.district_daily_statistics()["note"]


def test_daily_and_cumulative_selectors_do_not_mix_reporting_periods(daily_snapshot):
    dengue_day = next(row for row in daily.daily_statistics("daily") if row["disease"] == "Dengue")
    dengue_month = next(
        row for row in daily.daily_statistics("present_month") if row["disease"] == "Dengue"
    )
    dengue_total = next(
        row for row in daily.cumulative_statistics() if row["disease"] == "Dengue"
    )

    assert dengue_day["metric_period"] == "Daily"
    assert dengue_day["suspected_cases"] == 105
    assert dengue_day["suspected_deaths"] is None
    assert dengue_day["source_value_status"]["suspected_deaths"] == "source_dash_uninterpreted"
    assert dengue_month["metric_period"] == "Present Month"
    assert dengue_month["suspected_cases"] == 105
    assert dengue_total["metric_period"] == "Cumulative 2026"
    assert dengue_total["suspected_cases"] == 35419


def test_snapshot_is_retained_and_freshness_changes_after_refresh_failure(
    daily_snapshot, monkeypatch, tmp_path
):
    monkeypatch.setattr(daily, "ROOT", tmp_path)
    monkeypatch.setattr(daily, "DAILY_DIR", tmp_path / "daily")
    monkeypatch.setattr(daily, "SNAPSHOT_DIR", tmp_path / "daily" / "snapshots")
    monkeypatch.setattr(daily, "LATEST_PATH", tmp_path / "daily" / "latest.json")
    monkeypatch.setattr(daily, "STATUS_PATH", tmp_path / "daily" / "source_status.json")
    daily.record_daily_refresh_success(daily_snapshot)
    preserved = daily.LATEST_PATH.read_bytes()
    daily.record_daily_refresh_failure(
        "Official DHS source timeout.",
        attempted_at="2026-11-02T13:00:00+00:00",
    )

    assert daily.LATEST_PATH.read_bytes() == preserved
    assert daily.load_daily_snapshot()["report_date"] == "2026-11-01"
    assert daily.get_daily_source_status(as_of=date(2026, 11, 2))["status"] == "source_unavailable"
    assert daily.get_daily_source_status(as_of=date(2026, 11, 2))["last_attempt"]["cached_snapshot_retained"]
    assert daily.get_daily_source_status(as_of=date(2026, 11, 10))["status"] == "source_unavailable"


@pytest.mark.parametrize(
    ("as_of", "expected_status"),
    [
        (date(2026, 11, 3), "verified_recent"),
        (date(2026, 11, 4), "official_delayed"),
        (date(2026, 11, 8), "official_delayed"),
        (date(2026, 11, 9), "historical"),
    ],
)
def test_daily_freshness_uses_documented_report_date_thresholds(
    daily_snapshot, monkeypatch, as_of, expected_status
):
    monkeypatch.setattr(daily, "_read_json", lambda _path: {"last_attempt_status": "success"})
    monkeypatch.setattr(daily, "load_daily_snapshot", lambda: daily_snapshot)

    assert daily.get_daily_source_status(as_of=as_of)["status"] == expected_status


def test_daily_api_endpoints_and_historical_annual_separation():
    latest = client.get("/api/live-surveillance/daily/latest")
    daily_values = client.get("/api/live-surveillance/daily/diseases/daily")
    cumulative = client.get("/api/live-surveillance/daily/cumulative")
    districts = client.get(
        "/api/live-surveillance/daily/districts",
        params={"disease": "Dengue"},
    )
    source_status = client.get("/api/live-surveillance/daily/source-status")
    annual = client.get("/api/live-surveillance/summary")

    assert latest.status_code == daily_values.status_code == cumulative.status_code == 200
    assert latest.json()["report_date"] == "2026-11-01"
    assert latest.json()["is_live"] is False
    assert daily_values.json()["metric_period"] == "Daily"
    dengue_daily = next(
        row for row in daily_values.json()["records"] if row["disease"] == "Dengue"
    )
    assert dengue_daily["suspected_deaths"] is None
    assert dengue_daily["source_value_status"]["suspected_deaths"] == "source_dash_uninterpreted"
    assert cumulative.json()["metric_period"] == "Cumulative 2026"
    dengue_cumulative = next(
        row for row in cumulative.json()["records"] if row["disease"] == "Dengue"
    )
    assert dengue_cumulative["suspected_cases"] == 35419
    assert districts.json()["reported_district_count"] == 14
    age_days = (
        datetime.now(timezone.utc).date()
        - date.fromisoformat(source_status.json()["report_date"])
    ).days
    assert source_status.json()["status"] == freshness_status_for_age(age_days)
    assert source_status.json()["source_post_published_at"] == "2026-11-02T05:15:09+00:00"
    assert annual.status_code == 200
    assert annual.json()["reporting_period_end"] == "2025-12"
    assert annual.json()["current_2026_information_available"] is False


def test_daily_source_metadata_explicitly_disclaims_hospital_capacity_feed():
    response = client.get("/api/live-surveillance/daily/source")

    assert response.status_code == 200
    assert response.json()["hospital_capacity_data_connected"] is False
    assert "No verified official hospital bed occupancy" in response.json()["hospital_capacity_note"]


def test_methodology_endpoint_lists_daily_source_and_quality_report():
    response = client.get("/api/methodology")

    assert response.status_code == 200
    source = next(
        row for row in response.json()["sources"]
        if row["name"] == "Kerala DHS IDSP daily surveillance reports"
    )
    assert source["coverage"] == "2026-11-01"
    age_days = (
        datetime.now(timezone.utc).date()
        - date.fromisoformat(source["coverage"])
    ).days
    assert source["status"] == freshness_status_for_age(age_days)
    assert "reports/daily_idsp_data_quality_report.md" in response.json()["reports"]


def test_history_reports_missing_dates_without_inserting_observations(
    daily_snapshot, monkeypatch
):
    first = copy.deepcopy(daily_snapshot)
    second = copy.deepcopy(daily_snapshot)
    first["report_date"] = "2026-10-30"
    second["report_date"] = "2026-11-01"
    for snapshot in (first, second):
        snapshot["retrieved_at_utc"] = "2026-11-02T12:00:00+00:00"
        for record in snapshot["statewide_records"]:
            record["cumulative_2026"]["suspected_cases"] = 100000
    monkeypatch.setattr(daily, "load_daily_history", lambda: [first, second])

    series = daily.daily_time_series("Dengue")

    assert series["report_count"] == 2
    assert [row["report_date"] for row in series["records"]] == ["2026-10-30", "2026-11-01"]
    assert series["missing_report_dates"] == ["2026-10-31"]
    assert len(series["records"]) == 2
    assert "not zero-case observations" in series["note"]
    assert all(row["suspected_cases"] == 105 for row in series["records"])


def test_seven_day_and_thirty_day_summaries_require_complete_dates_and_numeric_values(
    monkeypatch,
):
    from datetime import timedelta

    end = date(2026, 11, 30)

    def make_records(start: date, count: int):
        rows = []
        for offset in range(count):
            report_date = start + timedelta(days=offset)
            rows.append({
                "report_date": report_date.isoformat(),
                "suspected_cases": 2,
                "suspected_deaths": 0,
                "confirmed_cases": 3,
                "confirmed_deaths": 0,
                "source_values": {},
                "source_value_status": {},
            })
        return rows

    records = make_records(date(2026, 11, 1), 30)
    monkeypatch.setattr(daily, "daily_time_series", lambda _disease: {"records": records})

    summary = daily.period_summary("Dengue", end_date=end, days=7)
    suspected = summary["metrics"]["suspected_cases"]
    assert suspected["current"]["complete"] is True
    assert suspected["previous"]["complete"] is True
    assert suspected["current"]["reported_total"] == 14
    assert suspected["current"]["comparison"]["absolute_change"] == 0

    records.pop(29)
    incomplete = daily.period_summary("Dengue", end_date=end, days=7)
    assert incomplete["metrics"]["suspected_cases"]["current"]["complete"] is False
    assert incomplete["metrics"]["suspected_cases"]["current"]["reported_total"] is None
    records.append({
        "report_date": "2026-11-30",
        "suspected_cases": 2,
        "suspected_deaths": 0,
        "confirmed_cases": 3,
        "confirmed_deaths": 0,
        "source_values": {},
        "source_value_status": {},
    })

    thirty = daily.period_summary("Dengue", end_date=end, days=30)
    assert thirty["metrics"]["suspected_cases"]["current"]["complete"] is True
    assert thirty["metrics"]["suspected_cases"]["current"]["reported_total"] == 60


def test_repeated_import_does_not_duplicate_archive_and_old_backfill_keeps_latest(
    daily_snapshot, monkeypatch, tmp_path
):
    monkeypatch.setattr(daily, "ROOT", tmp_path)
    monkeypatch.setattr(daily, "DAILY_DIR", tmp_path / "daily")
    monkeypatch.setattr(daily, "SNAPSHOT_DIR", tmp_path / "daily" / "snapshots")
    monkeypatch.setattr(daily, "LATEST_PATH", tmp_path / "daily" / "latest.json")
    monkeypatch.setattr(daily, "STATUS_PATH", tmp_path / "daily" / "source_status.json")
    daily.record_daily_refresh_success(daily_snapshot)
    before = len(list(daily.SNAPSHOT_DIR.glob("*.json")))
    daily.record_daily_refresh_success(daily_snapshot)
    assert len(list(daily.SNAPSHOT_DIR.glob("*.json"))) == before

    older = copy.deepcopy(daily_snapshot)
    older["report_date"] = "2026-07-25"
    older["retrieved_at_utc"] = "2026-11-02T12:10:00+00:00"
    older["dataset_version"] = f"idsp-v{daily.PARSER_VERSION}-{older['source_sha256'][:16]}"
    daily.record_daily_refresh_success(older)

    assert daily.load_daily_snapshot()["report_date"] == "2026-11-01"


def test_backfill_manifest_tracks_discovered_failures_and_calendar_gaps(
    daily_snapshot, monkeypatch, tmp_path
):
    post = {"report_date": "2026-11-01", "post_url": REPORT_POST_URL}
    monkeypatch.setattr(importer, "DAILY_DIR", tmp_path / "daily")
    monkeypatch.setattr(importer, "load_daily_history", lambda: [])
    monkeypatch.setattr(importer, "discover_reports", lambda *_args: [post])
    monkeypatch.setattr(importer, "_fetch_html", lambda *_args: "<a href='https://dhs.kerala.gov.in/report.pdf'>PDF</a>")
    monkeypatch.setattr(importer, "extract_post_published_at", lambda *_args: None)
    monkeypatch.setattr(importer, "discover_pdf_link", lambda *_args: REPORT_PDF_URL)
    monkeypatch.setattr(importer, "_fetch_pdf", lambda *_args: (_ for _ in ()).throw(importer.ReportImportError("PDF unavailable")))
    monkeypatch.setattr(importer, "record_daily_refresh_failure", lambda *_args: None)
    monkeypatch.setattr(importer, "retrieve_candidate_report", lambda *_args: daily_snapshot)

    manifest = importer.backfill_2026_reports(
        session=object(),
        request_delay_seconds=0,
    )

    assert manifest["discovered_2026_post_count"] == 1
    assert manifest["imported_date_count"] == 1
    assert manifest["discovered_report_dates"] == ["2026-11-01"]
    assert manifest["calendar_dates_not_listed_by_index"][0] == "2026-01-01"
    assert manifest["calendar_dates_not_listed_by_index"][-1] == "2026-10-31"
