"""Read-only access to verified, manually imported Kerala DHS surveillance reports."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LIVE_DIR = ROOT / "data" / "live_surveillance"
SNAPSHOT_DIR = LIVE_DIR / "snapshots"
LATEST_PATH = LIVE_DIR / "latest.json"
STATUS_PATH = LIVE_DIR / "source_status.json"
SOURCE_ID = "kerala_dhs_communicable_disease_annual_pdf"
SOURCE_NAME = "Kerala Directorate of Health Services — Data on Communicable Diseases"
SOURCE_INDEX_URL = "https://dhs.kerala.gov.in/en/data-on-communicable-diseases/"
SOURCE_PDF_URL = (
    "https://dhs.kerala.gov.in/wp-content/uploads/2026/09/CD-Data-2025-Approved.pdf"
)
PARSER_VERSION = 3
HISTORICAL_START = "2021-01"
HISTORICAL_END = "2024-12"
EXPECTED_DISTRICTS = (
    "Thiruvananthapuram",
    "Kollam",
    "Pathanamthitta",
    "Alappuzha",
    "Kottayam",
    "Idukki",
    "Ernakulam",
    "Thrissur",
    "Palakkad",
    "Malappuram",
    "Kozhikode",
    "Wayanad",
    "Kannur",
    "Kasaragod",
)


class SurveillanceUnavailable(Exception):
    """The official-report snapshot is absent or invalid."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SurveillanceUnavailable(f"Could not read surveillance metadata {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SurveillanceUnavailable(f"Surveillance metadata is not a JSON object: {path}")
    return value


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    if snapshot.get("schema_version") != 1:
        raise SurveillanceUnavailable("Unsupported live-surveillance snapshot schema.")
    if snapshot.get("source_id") != SOURCE_ID:
        raise SurveillanceUnavailable("Snapshot source identifier does not match the verified DHS source.")
    if snapshot.get("reporting_period") != "2025":
        raise SurveillanceUnavailable("Snapshot reporting period is not the verified 2025 report.")
    if snapshot.get("source_url") != SOURCE_PDF_URL:
        raise SurveillanceUnavailable("Snapshot URL is not the verified DHS report URL.")
    if snapshot.get("frequency") != "annual report with monthly statewide tables":
        raise SurveillanceUnavailable("Snapshot reporting frequency metadata is invalid.")
    if snapshot.get("validation_status") not in {"passed", "passed_with_quality_flags"}:
        raise SurveillanceUnavailable("Snapshot has not passed report validation.")
    digest = snapshot.get("source_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise SurveillanceUnavailable("Snapshot source SHA-256 is missing or invalid.")
    if snapshot.get("dataset_version") != f"report-v{PARSER_VERSION}-sha256-{digest[:16]}":
        raise SurveillanceUnavailable("Snapshot version does not match the preserved source hash.")
    records = snapshot.get("monthly_records")
    districts = snapshot.get("district_annual_records")
    statewide = snapshot.get("statewide_annual_records")
    if not isinstance(records, list) or not isinstance(districts, list) or not isinstance(statewide, list):
        raise SurveillanceUnavailable("Snapshot is missing required official report tables.")
    if not records or not districts or not statewide:
        raise SurveillanceUnavailable("Snapshot contains an empty required report table.")
    _validate_records(
        records,
        "monthly",
        ("period", "disease", "classification", "source_label", "cases", "deaths"),
        ("period", "disease", "classification"),
    )
    _validate_records(
        statewide,
        "statewide annual",
        ("year", "disease", "classification", "source_label", "cases"),
        ("year", "disease", "classification", "metric_unit"),
    )
    _validate_records(
        districts,
        "district annual",
        ("year", "district", "disease", "classification", "cases"),
        ("year", "district", "disease", "classification", "metric_unit"),
    )

    for row in records:
        if not isinstance(row["period"], str) or not _is_valid_month(row["period"]):
            raise SurveillanceUnavailable("Monthly report contains an invalid reporting period.")
        if not row.get("disease") or not row.get("classification") or not row.get("source_label"):
            raise SurveillanceUnavailable("Monthly report contains missing disease/source classifications.")
        _validate_count(row["cases"], "monthly cases")
        _validate_count(row["deaths"], "monthly deaths")

    monthly_series: dict[tuple[str, str], set[str]] = {}
    for row in records:
        monthly_series.setdefault((row["disease"], row["classification"]), set()).add(row["period"])
    expected_months = {f"2025-{month:02d}" for month in range(1, 13)}
    if any(months != expected_months for months in monthly_series.values()):
        raise SurveillanceUnavailable("A published monthly disease series has missing reporting months.")

    for row in statewide:
        if row.get("year") != 2025:
            raise SurveillanceUnavailable("Statewide annual record has an unexpected reporting year.")
        if (
            not row.get("disease")
            or not row.get("classification")
            or not row.get("source_label")
            or not row.get("metric_unit")
        ):
            raise SurveillanceUnavailable("Statewide annual report contains missing disease labels.")
        _validate_count(row["cases"], "statewide annual cases")
        if row["deaths"] is not None:
            _validate_count(row["deaths"], "statewide annual deaths")

    for row in districts:
        if row.get("year") != 2025:
            raise SurveillanceUnavailable("District record has an unexpected reporting year.")
        if row.get("district") not in EXPECTED_DISTRICTS:
            raise SurveillanceUnavailable(f"Unknown official district label: {row.get('district')!r}.")
        if not row.get("disease") or not row.get("classification") or not row.get("metric_unit"):
            raise SurveillanceUnavailable("District report contains missing disease/source classifications.")
        _validate_count(row["cases"], "district annual cases")
        if row.get("deaths") is not None:
            _validate_count(row["deaths"], "district annual deaths")

    quality_flags = find_suspicious_value_flags(snapshot)
    if snapshot.get("suspicious_value_flags") != quality_flags:
        raise SurveillanceUnavailable("Snapshot suspicious-value flags do not match its records.")
    expected_validation_status = "passed_with_quality_flags" if quality_flags else "passed"
    if snapshot.get("validation_status") != expected_validation_status:
        raise SurveillanceUnavailable("Snapshot validation status does not match its quality flags.")

    months = {row["period"] for row in records}
    if months != {f"2025-{month:02d}" for month in range(1, 13)}:
        raise SurveillanceUnavailable("Official monthly report must contain all 12 explicitly reported 2025 months.")
    district_names = {row["district"] for row in districts}
    if not district_names.issubset(set(EXPECTED_DISTRICTS)):
        raise SurveillanceUnavailable("District names do not map to the official Kerala district list.")
    if snapshot.get("reported_districts") != sorted(district_names):
        raise SurveillanceUnavailable("Snapshot district coverage metadata does not match district records.")
    expected_missing = sorted(set(EXPECTED_DISTRICTS) - district_names)
    if snapshot.get("missing_districts") != expected_missing:
        raise SurveillanceUnavailable("Snapshot missing-district metadata does not match report coverage.")
    if snapshot.get("publication_date") is not None:
        if not _is_valid_date(snapshot["publication_date"]):
            raise SurveillanceUnavailable("Source publication date is invalid.")
    if snapshot.get("last_modified_date") is not None and not _is_valid_date(
        snapshot["last_modified_date"]
    ):
        raise SurveillanceUnavailable("Source last-modified date is invalid.")
    retrieval = snapshot.get("retrieved_at_utc")
    if not isinstance(retrieval, str):
        raise SurveillanceUnavailable("Snapshot retrieval timestamp is missing.")
    try:
        parsed_retrieval = datetime.fromisoformat(retrieval.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SurveillanceUnavailable("Snapshot retrieval timestamp is invalid.") from exc
    if parsed_retrieval.tzinfo is None:
        raise SurveillanceUnavailable("Snapshot retrieval timestamp must include a timezone.")


def _validate_records(
    records: list[Any],
    label: str,
    required_fields: tuple[str, ...],
    natural_key: tuple[str, ...],
) -> None:
    seen: set[tuple[Any, ...]] = set()
    for row in records:
        if not isinstance(row, dict):
            raise SurveillanceUnavailable(f"{label} table contains a non-object record.")
        missing = [key for key in (*required_fields, *natural_key) if key not in row or row[key] is None]
        if missing:
            raise SurveillanceUnavailable(
                f"{label} table has missing required values: {', '.join(missing)}."
            )
        key = tuple(row[column] for column in natural_key)
        try:
            hash(key)
        except TypeError as exc:
            raise SurveillanceUnavailable(
                f"{label} table contains non-scalar natural-key values."
            ) from exc
        if key in seen:
            raise SurveillanceUnavailable(f"{label} table contains duplicate natural keys.")
        seen.add(key)


def _validate_count(value: Any, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SurveillanceUnavailable(f"{label} is missing or non-numeric.")
    if not math.isfinite(value) or value < 0 or int(value) != value:
        raise SurveillanceUnavailable(f"{label} is negative, non-finite, or not a whole count.")


def find_suspicious_value_flags(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    flags = []
    for table_name, records in (
        ("monthly statewide", snapshot.get("monthly_records", [])),
        ("statewide annual", snapshot.get("statewide_annual_records", [])),
        ("district annual", snapshot.get("district_annual_records", [])),
    ):
        for row in records:
            cases = row.get("cases")
            deaths = row.get("deaths")
            if (
                isinstance(cases, (int, float))
                and not isinstance(cases, bool)
                and isinstance(deaths, (int, float))
                and not isinstance(deaths, bool)
                and deaths > cases
            ):
                flags.append({
                    "table": table_name,
                    "period": row.get("period", row.get("year")),
                    "district": row.get("district"),
                    "disease": row.get("disease"),
                    "classification": row.get("classification"),
                    "cases": cases,
                    "deaths": deaths,
                    "reason": "Reported deaths exceed reported cases; retained for source review.",
                })
    return flags


def _is_valid_month(value: str) -> bool:
    try:
        year_text, month_text = value.split("-")
        return len(year_text) == 4 and len(month_text) == 2 and 1 <= int(month_text) <= 12
    except (ValueError, AttributeError):
        return False


def _is_valid_date(value: Any) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def load_snapshot() -> dict[str, Any]:
    if not LATEST_PATH.is_file():
        raise SurveillanceUnavailable(
            "Current official data unavailable: no verified official-report snapshot has been imported."
        )
    snapshot = _read_json(LATEST_PATH)
    validate_snapshot(snapshot)
    return snapshot


def get_source_status(as_of: date | None = None) -> dict[str, Any]:
    try:
        snapshot = load_snapshot()
    except SurveillanceUnavailable as exc:
        status = {}
        if STATUS_PATH.is_file():
            status = _read_json(STATUS_PATH)
        return {
            "status": "data_not_available",
            "source_access_status": status.get("last_attempt_status", "not_retrieved"),
            "source_name": SOURCE_NAME,
            "source_index_url": SOURCE_INDEX_URL,
            "source_url": SOURCE_PDF_URL,
            "snapshot_available": False,
            "last_successful_retrieval": None,
            "publication_date": None,
            "publication_date_note": "No verified official-report snapshot is available.",
            "last_modified_date": None,
            "reporting_period": None,
            "reporting_period_start": None,
            "reporting_period_end": None,
            "frequency": "Annual report with monthly tables when published",
            "last_attempt": status.get("last_attempt"),
            "error": str(exc),
            "freshness_rule": _freshness_rule(),
        }

    attempt = _read_json(STATUS_PATH) if STATUS_PATH.is_file() else {}
    period_end = date(2025, 12, 31)
    retrieval_date = as_of or datetime.now(timezone.utc).date()
    report_age_days = (retrieval_date - period_end).days
    if attempt.get("last_attempt_status") == "unavailable":
        status_code = "source_unavailable"
    elif report_age_days > 730:
        status_code = "historical"
    elif report_age_days > 90:
        status_code = "official_delayed"
    else:
        status_code = "verified_recent"
    return {
        "status": status_code,
        "source_access_status": attempt.get("last_attempt_status", "snapshot_available"),
        "source_name": SOURCE_NAME,
        "source_index_url": SOURCE_INDEX_URL,
        "source_url": snapshot["source_url"],
        "source_document": snapshot["source_document"],
        "source_id": SOURCE_ID,
        "snapshot_available": True,
        "publication_date": snapshot.get("publication_date"),
        "publication_date_note": snapshot.get("publication_date_note"),
        "last_modified_date": snapshot.get("last_modified_date"),
        "reporting_period": snapshot["reporting_period"],
        "reporting_period_start": "2025-01",
        "reporting_period_end": "2025-12",
        "frequency": snapshot["frequency"],
        "last_successful_retrieval": snapshot["retrieved_at_utc"],
        "retrieval_timestamp_basis": snapshot.get("retrieval_timestamp_basis"),
        "source_response_date": snapshot.get("source_response_date"),
        "last_attempt": attempt.get("last_attempt"),
        "dataset_version": snapshot["dataset_version"],
        "source_sha256": snapshot["source_sha256"],
        "reported_district_count": len(snapshot["reported_districts"]),
        "expected_district_count": len(EXPECTED_DISTRICTS),
        "missing_districts": snapshot["missing_districts"],
        "statewide_district_reconciliation": snapshot["district_reconciliation"],
        "freshness_rule": _freshness_rule(),
        "message": (
            "Latest verified official report is an annual report through December 2025. "
            "It is not a live 2026 feed; 2026 surveillance data are not available in this snapshot."
        ),
    }


def _freshness_rule() -> dict[str, Any]:
    return {
        "reporting_frequency": "Annual official DHS report; includes monthly tables for the report year.",
        "official_delayed": (
            "A verified official report is shown as delayed when its reporting period ends more than "
            "90 days before the source file's last-modified date. Annual reporting is not expected daily."
        ),
        "historical": "Report-period end is more than 24 months before the current date.",
        "verified_recent": (
            "Reserved for an official source with a verified publication/retrieval period no more than "
            "90 days old and a declared reporting cadence; not applicable to this annual snapshot."
        ),
    }


def latest_summary(snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    if snapshot is None:
        try:
            snapshot = load_snapshot()
        except SurveillanceUnavailable:
            source_status = get_source_status()
            return {
                "data_status": "data_not_available",
                "snapshot_data_status": "data_not_available",
                "is_live": False,
                "current_2026_information_available": False,
                "reporting_period_start": None,
                "reporting_period_end": None,
                "source_publication_date": None,
                "source_publication_date_note": "No verified official-report snapshot is available.",
                "last_successful_retrieval": None,
                "source_status": source_status,
                "verified_disease_count": 0,
                "verified_monthly_series_count": 0,
                "district_count": 0,
                "expected_district_count": len(EXPECTED_DISTRICTS),
                "missing_districts": list(EXPECTED_DISTRICTS),
                "disease_statistics": [],
                "message": "Current official data unavailable. No snapshot has been imported.",
            }
    validate_snapshot(snapshot)
    period = max(row["period"] for row in snapshot["monthly_records"])
    previous_period = _previous_month(period)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in snapshot["monthly_records"]:
        grouped.setdefault((record["disease"], record["classification"]), []).append(record)
    cards = []
    for (disease, classification), records in sorted(grouped.items()):
        by_period = {row["period"]: row for row in records}
        current = by_period.get(period)
        previous = by_period.get(previous_period)
        if current is None:
            continue
        cases_change = current["cases"] - previous["cases"] if previous else None
        deaths_change = (
            current["deaths"] - previous["deaths"]
            if previous and current.get("deaths") is not None and previous.get("deaths") is not None
            else None
        )
        cards.append({
            "disease": disease,
            "classification": classification,
            "source_label": current["source_label"],
            "latest_period": period,
            "previous_comparable_period": previous_period if previous else None,
            "cases": current["cases"],
            "previous_cases": previous["cases"] if previous else None,
            "cases_change": cases_change,
            "cases_change_percent": (
                round(cases_change / previous["cases"] * 100, 2)
                if previous and previous["cases"] != 0 and cases_change is not None
                else None
            ),
            "deaths": current.get("deaths"),
            "previous_deaths": previous.get("deaths") if previous else None,
            "deaths_change": deaths_change,
            "change_interpretation": _interpret_change(cases_change),
            "comparison_valid": previous is not None,
            "source_name": snapshot["source_name"],
            "source_url": snapshot["source_url"],
            "data_status": "official_delayed",
            "metric_unit": current.get("metric_unit", "reported cases"),
        })
    return {
        "data_status": get_source_status()["status"],
        "snapshot_data_status": "official_delayed",
        "is_live": False,
        "current_2026_information_available": False,
        "reporting_period_start": "2025-01",
        "reporting_period_end": "2025-12",
        "source_publication_date": snapshot.get("publication_date"),
        "source_publication_date_note": snapshot.get("publication_date_note"),
        "last_successful_retrieval": snapshot["retrieved_at_utc"],
        "source_status": get_source_status(),
        "verified_disease_count": len({
            row["disease"] for row in snapshot["monthly_records"]
            if not row["disease"].startswith("Fever (Undifferentiated)")
        }),
        "verified_monthly_series_count": len({
            (row["disease"], row["classification"])
            for row in snapshot["monthly_records"]
        }),
        "district_count": len(snapshot["reported_districts"]),
        "expected_district_count": len(EXPECTED_DISTRICTS),
        "missing_districts": snapshot["missing_districts"],
        "disease_statistics": cards,
    }


def _previous_month(period: str) -> str:
    year, month = (int(value) for value in period.split("-"))
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def _interpret_change(change: int | None) -> str:
    if change is None:
        return "No previous comparable month is available."
    if change > 0:
        return "Reported cases increased compared with the previous comparable reporting period."
    if change < 0:
        return "Reported cases decreased compared with the previous comparable reporting period."
    return "Reported cases were unchanged from the previous comparable reporting period."


def disease_statistics(
    disease: str | None = None,
    classification: str | None = None,
) -> list[dict[str, Any]]:
    summary = latest_summary()
    records = summary["disease_statistics"]
    return [
        row for row in records
        if (disease is None or row["disease"].casefold() == disease.casefold())
        and (classification is None or row["classification"].casefold() == classification.casefold())
    ]


def district_statistics(
    disease: str | None = None,
    classification: str | None = None,
) -> dict[str, Any]:
    snapshot = load_snapshot()
    rows = [
        row for row in snapshot["district_annual_records"]
        if (disease is None or row["disease"].casefold() == disease.casefold())
        and (
            classification is None
            or row["classification"].casefold() == classification.casefold()
        )
    ]
    rows.sort(key=lambda row: (-row["cases"], row["district"]))
    for rank, row in enumerate(rows, start=1):
        row["rank_by_reported_count"] = rank
    return {
        "reporting_year": 2025,
        "reporting_frequency": "Annual",
        "temporal_granularity": "annual district records, not district-month",
        "disease": disease,
        "classification": classification,
        "records": rows,
        "reported_districts": snapshot["reported_districts"],
        "missing_districts": snapshot["missing_districts"],
        "expected_district_count": len(EXPECTED_DISTRICTS),
        "comparison_note": (
            "Sorted by reported absolute counts only. High counts are not a risk classification; "
            "no population denominator is available."
        ),
        "source_url": snapshot["source_url"],
    }


def trend_records(
    disease: str | None = None,
    classification: str | None = None,
) -> list[dict[str, Any]]:
    snapshot = load_snapshot()
    return [
        row for row in snapshot["monthly_records"]
        if (disease is None or row["disease"].casefold() == disease.casefold())
        and (
            classification is None
            or row["classification"].casefold() == classification.casefold()
        )
    ]


def dataset_info(snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    snapshot = snapshot or load_snapshot()
    return {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "source_url": snapshot["source_url"],
        "source_index_url": SOURCE_INDEX_URL,
        "retrieval_method": snapshot["retrieval_method"],
        "reporting_frequency": snapshot["frequency"],
        "publication_date": snapshot.get("publication_date"),
        "publication_date_note": snapshot.get("publication_date_note"),
        "last_modified_date": snapshot.get("last_modified_date"),
        "last_retrieval_timestamp": snapshot["retrieved_at_utc"],
        "retrieval_timestamp_basis": snapshot.get("retrieval_timestamp_basis"),
        "source_response_date": snapshot.get("source_response_date"),
        "reporting_period": snapshot["reporting_period"],
        "available_variables": snapshot["available_variables"],
        "reported_districts": snapshot["reported_districts"],
        "missing_districts": snapshot["missing_districts"],
        "validation_status": snapshot["validation_status"],
        "validation_checks": snapshot["validation_checks"],
        "suspicious_value_flags": snapshot["suspicious_value_flags"],
        "limitations": snapshot["limitations"],
        "dataset_version": snapshot["dataset_version"],
        "source_sha256": snapshot["source_sha256"],
        "source_access_status": get_source_status()["source_access_status"],
    }


def record_refresh_failure(message: str, attempted_at: str | None = None) -> None:
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    status = _read_json(STATUS_PATH) if STATUS_PATH.is_file() else {}
    status["last_attempt_status"] = "unavailable"
    status["last_attempt"] = {
        "timestamp_utc": attempted_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "unavailable",
        "error": message[:1000],
        "cached_snapshot_retained": LATEST_PATH.is_file(),
    }
    _atomic_write_json(STATUS_PATH, status)


def record_refresh_success(snapshot: dict[str, Any]) -> None:
    validate_snapshot(snapshot)
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    retrieved = datetime.fromisoformat(snapshot["retrieved_at_utc"].replace("Z", "+00:00"))
    retrieval_id = retrieved.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = (
        f"dhs_{snapshot['reporting_period']}_{snapshot['dataset_version']}_"
        f"{retrieval_id}.json"
    )
    archived = SNAPSHOT_DIR / filename
    if archived.is_file():
        archived_snapshot = _read_json(archived)
        validate_snapshot(archived_snapshot)
        if archived_snapshot["source_sha256"] != snapshot["source_sha256"]:
            raise SurveillanceUnavailable("Versioned DHS snapshot exists with a different source hash.")
    else:
        _atomic_write_json(archived, snapshot)
    _atomic_write_json(LATEST_PATH, snapshot)
    status = _read_json(STATUS_PATH) if STATUS_PATH.is_file() else {}
    status.update({
        "last_attempt_status": "success",
        "last_attempt": {
            "timestamp_utc": snapshot["retrieved_at_utc"],
            "status": "success",
            "dataset_version": snapshot["dataset_version"],
            "snapshot_file": archived.relative_to(ROOT).as_posix(),
            "cached_snapshot_retained": True,
        },
        "latest_snapshot_file": archived.relative_to(ROOT).as_posix(),
        "latest_snapshot_version": snapshot["dataset_version"],
    })
    _atomic_write_json(STATUS_PATH, status)


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
