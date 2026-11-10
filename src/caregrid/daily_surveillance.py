"""Validated read access to daily Kerala DHS IDSP report snapshots."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DAILY_DIR = ROOT / "data" / "live_surveillance" / "daily_idsp"
SNAPSHOT_DIR = DAILY_DIR / "snapshots"
LATEST_PATH = DAILY_DIR / "latest.json"
STATUS_PATH = DAILY_DIR / "source_status.json"
INDEX_URL = "https://dhs.kerala.gov.in/en/idsp-2/"
PARSER_VERSION = 3
EXPECTED_DISTRICT_CODES = {
    "TVM": "Thiruvananthapuram",
    "KLM": "Kollam",
    "PTA": "Pathanamthitta",
    "IDK": "Idukki",
    "KTM": "Kottayam",
    "ALP": "Alappuzha",
    "EKM": "Ernakulam",
    "TSR": "Thrissur",
    "PKD": "Palakkad",
    "MPM": "Malappuram",
    "KKD": "Kozhikode",
    "WYD": "Wayanad",
    "KNR": "Kannur",
    "KSD": "Kasaragod",
}


class DailySurveillanceUnavailable(Exception):
    """The daily IDSP snapshot is missing or invalid."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DailySurveillanceUnavailable(f"Could not read daily IDSP metadata {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DailySurveillanceUnavailable(f"Daily IDSP metadata is not a JSON object: {path}")
    return value


def validate_daily_snapshot(snapshot: dict[str, Any]) -> None:
    if snapshot.get("schema_version") != 1:
        raise DailySurveillanceUnavailable("Unsupported daily IDSP snapshot schema.")
    if snapshot.get("source_id") != "kerala_dhs_idsp_daily_pdf":
        raise DailySurveillanceUnavailable("Daily snapshot source ID is not the verified DHS IDSP source.")
    report_date = _valid_report_date(snapshot.get("report_date"))
    if report_date is None or snapshot.get("report_date") != report_date:
        raise DailySurveillanceUnavailable("Daily IDSP report date is missing or invalid.")
    if snapshot.get("parser_version") != PARSER_VERSION:
        raise DailySurveillanceUnavailable("Daily IDSP snapshot parser version is unsupported.")
    digest = snapshot.get("source_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise DailySurveillanceUnavailable("Daily report SHA-256 is missing or invalid.")
    if snapshot.get("dataset_version") != f"idsp-v{PARSER_VERSION}-{digest[:16]}":
        raise DailySurveillanceUnavailable("Daily report version does not match the source hash.")
    if snapshot.get("validation_status") not in {"passed", "passed_with_quality_flags"}:
        raise DailySurveillanceUnavailable("Daily report has not passed validation.")
    for key in ("source_page_url", "source_url"):
        if not isinstance(snapshot.get(key), str) or not snapshot[key].startswith("https://dhs.kerala.gov.in/"):
            raise DailySurveillanceUnavailable(f"Daily report {key} is not an HTTPS DHS URL.")
    retrieval = snapshot.get("retrieved_at_utc")
    if not isinstance(retrieval, str):
        raise DailySurveillanceUnavailable("Daily report retrieval timestamp is missing.")
    try:
        parsed_retrieval = datetime.fromisoformat(retrieval.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DailySurveillanceUnavailable("Daily report retrieval timestamp is invalid.") from exc
    if parsed_retrieval.tzinfo is None:
        raise DailySurveillanceUnavailable("Daily report retrieval timestamp must include a timezone.")
    if date.fromisoformat(report_date) > parsed_retrieval.date():
        raise DailySurveillanceUnavailable("Daily report date is later than the retrieval date.")
    published = snapshot.get("source_post_published_at")
    if published is not None:
        if not isinstance(published, str):
            raise DailySurveillanceUnavailable("DHS post publication timestamp is invalid.")
        try:
            published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError as exc:
            raise DailySurveillanceUnavailable("DHS post publication timestamp is invalid.") from exc
        if published_at.tzinfo is None:
            raise DailySurveillanceUnavailable("DHS post publication timestamp must include a timezone.")

    statewide = snapshot.get("statewide_records")
    districts = snapshot.get("district_records")
    if not isinstance(statewide, list) or not statewide:
        raise DailySurveillanceUnavailable("Daily report has no statewide data records.")
    if not isinstance(districts, list):
        raise DailySurveillanceUnavailable("Daily report district records must be a list.")
    _validate_records(
        statewide,
        "statewide",
        ("disease", "source_label", "source_values"),
        ("disease", "disease_subtype"),
    )
    periods = ("daily", "present_month", "cumulative_2026")
    count_fields = (
        "suspected_cases",
        "suspected_deaths",
        "confirmed_cases",
        "confirmed_deaths",
    )
    for row in statewide:
        if not row.get("disease") or not isinstance(row.get("source_label"), str):
            raise DailySurveillanceUnavailable("Statewide IDSP row has missing disease/source labels.")
        values = row.get("source_values")
        if not isinstance(values, dict):
            raise DailySurveillanceUnavailable("Statewide IDSP row is missing raw source values.")
        for period in periods:
            period_values = row.get(period)
            raw_period_values = values.get(period)
            if not isinstance(period_values, dict) or not isinstance(raw_period_values, dict):
                raise DailySurveillanceUnavailable(f"Statewide IDSP row is missing {period} fields.")
            for field in count_fields:
                _validate_optional_count(period_values.get(field), f"{period} {field}")
                if field not in raw_period_values:
                    raise DailySurveillanceUnavailable(f"Raw source value is missing {period} {field}.")
                status_values = row.get("source_value_status", {}).get(period, {})
                status = status_values.get(field) if isinstance(status_values, dict) else None
                raw_value = raw_period_values[field]
                expected_status = (
                    "source_dash_uninterpreted" if raw_value == "-"
                    else "not_reported" if raw_value in {"", "–", "—"}
                    else "reported"
                )
                if status != expected_status:
                    raise DailySurveillanceUnavailable(
                        f"Statewide {period} {field} status does not match the retained source value."
                    )
                if expected_status != "reported" and period_values[field] is not None:
                    raise DailySurveillanceUnavailable(
                        f"Statewide {period} {field} has a numeric value despite being missing or dashed."
                    )

    for key in ("daily_district_report_available",):
        if not isinstance(snapshot.get(key), bool):
            raise DailySurveillanceUnavailable(f"Daily snapshot {key} must be a boolean.")
    if snapshot["daily_district_report_available"]:
        _validate_records(
            districts,
            "district",
            (
                "district_code",
                "district",
                "disease",
                "source_label",
                "source_values",
            ),
            ("district_code", "disease", "disease_subtype"),
        )
        district_codes = {row["district_code"] for row in districts}
        if not district_codes or not district_codes.issubset(EXPECTED_DISTRICT_CODES):
            raise DailySurveillanceUnavailable("District daily report has no valid official district coverage.")
        for row in districts:
            if EXPECTED_DISTRICT_CODES.get(row["district_code"]) != row["district"]:
                raise DailySurveillanceUnavailable("Daily report district code/name mapping is invalid.")
            for field in ("suspected_cases", "confirmed_cases", "reported_deaths"):
                _validate_optional_count(row.get(field), f"district {field}")
            raw_values = row["source_values"]
            status_values = row.get("source_value_status")
            if not isinstance(status_values, dict):
                raise DailySurveillanceUnavailable("District source value statuses are missing.")
            for column, raw_value in raw_values.items():
                expected_status = (
                    "source_dash_uninterpreted" if raw_value == "-"
                    else "not_reported" if raw_value in {"", "–", "—"}
                    else "reported"
                )
                if status_values.get(column) != expected_status:
                    raise DailySurveillanceUnavailable(
                        "District source value status does not match its retained source cell."
                    )
            field_status = row.get("field_source_status")
            if not isinstance(field_status, dict):
                raise DailySurveillanceUnavailable("District metric statuses are missing.")
            for field, status in field_status.items():
                if field not in {
                    "suspected_cases",
                    "confirmed_cases",
                    "suspected_deaths",
                    "confirmed_deaths",
                    "reported_cases",
                    "reported_deaths",
                } or status not in {
                    "reported",
                    "source_dash_uninterpreted",
                    "not_reported",
                }:
                    raise DailySurveillanceUnavailable("District metric status is unsupported.")
    elif districts:
        raise DailySurveillanceUnavailable("Unavailable district reporting cannot contain district records.")

    flags = find_daily_quality_flags(snapshot)
    if snapshot.get("quality_flags") != flags:
        raise DailySurveillanceUnavailable("Daily report quality flags do not match its values.")
    expected_status = "passed_with_quality_flags" if flags else "passed"
    if snapshot.get("validation_status") != expected_status:
        raise DailySurveillanceUnavailable("Daily report validation status does not match its quality flags.")


def _valid_report_date(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _validate_records(
    rows: list[Any],
    label: str,
    required: tuple[str, ...],
    natural_key: tuple[str, ...],
) -> None:
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise DailySurveillanceUnavailable(f"{label} report contains a non-object record.")
        missing = [key for key in required if key not in row or row[key] is None]
        if missing:
            raise DailySurveillanceUnavailable(
                f"{label} report row is missing required fields: {', '.join(missing)}."
            )
        key = tuple(row.get(field) for field in natural_key)
        try:
            hash(key)
        except TypeError as exc:
            raise DailySurveillanceUnavailable(f"{label} report has non-scalar duplicate keys.") from exc
        if key in seen:
            raise DailySurveillanceUnavailable(f"{label} report has duplicate natural keys.")
        seen.add(key)


def _validate_optional_count(value: Any, label: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DailySurveillanceUnavailable(f"{label} is not numeric.")
    if not math.isfinite(value) or value < 0 or int(value) != value:
        raise DailySurveillanceUnavailable(f"{label} is negative, non-finite, or not a whole count.")


def find_daily_quality_flags(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    flags = []
    for row in snapshot.get("statewide_records", []):
        for period in ("daily", "present_month", "cumulative_2026"):
            values = row.get(period, {})
            suspected = values.get("suspected_cases")
            confirmed = values.get("confirmed_cases")
            if suspected is not None and confirmed is not None and confirmed > suspected:
                flags.append({
                    "scope": "statewide",
                    "period": period,
                    "disease": row.get("disease"),
                    "disease_subtype": row.get("disease_subtype"),
                    "reason": "Confirmed cases exceed suspected cases; values retained as source reported.",
                })
    for row in snapshot.get("district_reconciliation", []):
        if row.get("reconciles") is not True:
            flags.append({
                "scope": "district_reconciliation",
                "disease": row.get("disease"),
                "classification": row.get("classification"),
                "reason": (
                    "District aggregate cannot be reconciled because source cells are missing."
                    if row.get("district_sum") is None
                    else "District sum differs from the source aggregate; both values are retained."
                ),
            })
    return flags


def load_daily_snapshot() -> dict[str, Any]:
    if not LATEST_PATH.is_file():
        raise DailySurveillanceUnavailable(
            "Current daily IDSP data unavailable: no verified daily report snapshot has been imported."
        )
    snapshot = _read_json(LATEST_PATH)
    validate_daily_snapshot(snapshot)
    return snapshot


def get_daily_source_status(as_of: date | None = None) -> dict[str, Any]:
    attempt = _read_json(STATUS_PATH) if STATUS_PATH.is_file() else {}
    try:
        snapshot = load_daily_snapshot()
    except DailySurveillanceUnavailable as exc:
        return {
            "status": "data_not_available",
            "source_access_status": attempt.get("last_attempt_status", "not_retrieved"),
            "source_name": "Kerala Directorate of Health Services — IDSP daily reports",
            "source_index_url": INDEX_URL,
            "snapshot_available": False,
            "last_successful_retrieval": None,
            "last_attempt": attempt.get("last_attempt"),
            "error": str(exc),
            "freshness_rule": _daily_freshness_rule(),
            "daily_district_report_available": False,
            "reported_district_count": 0,
            "expected_district_count": len(EXPECTED_DISTRICT_CODES),
        }
    report_date = date.fromisoformat(snapshot["report_date"])
    current_date = as_of or datetime.now(timezone.utc).date()
    age = (current_date - report_date).days
    if attempt.get("last_attempt_status") == "unavailable":
        status = "source_unavailable"
    elif age <= 2:
        status = "verified_recent"
    elif age <= 7:
        status = "official_delayed"
    else:
        status = "historical"
    return {
        "status": status,
        "source_access_status": attempt.get("last_attempt_status", "success"),
        "source_name": snapshot["source_name"],
        "source_index_url": snapshot["source_index_url"],
        "source_page_url": snapshot["source_page_url"],
        "source_post_published_at": snapshot.get("source_post_published_at"),
        "source_url": snapshot["source_url"],
        "source_document": snapshot["source_document"],
        "snapshot_available": True,
        "report_date": snapshot["report_date"],
        "last_successful_retrieval": snapshot["retrieved_at_utc"],
        "last_attempt": attempt.get("last_attempt"),
        "dataset_version": snapshot["dataset_version"],
        "source_sha256": snapshot["source_sha256"],
        "parser_version": snapshot["parser_version"],
        "daily_district_report_available": snapshot["daily_district_report_available"],
        "reported_district_count": len(snapshot["reported_district_codes"]),
        "expected_district_count": len(EXPECTED_DISTRICT_CODES),
        "district_codes": snapshot["reported_district_codes"],
        "missing_district_codes": sorted(
            set(EXPECTED_DISTRICT_CODES) - set(snapshot["reported_district_codes"])
        ),
        "freshness_rule": _daily_freshness_rule(),
        "provisional_warning": snapshot["provisional_warning"],
    }


def _daily_freshness_rule() -> dict[str, str]:
    return {
        "reporting_frequency": "Daily IDSP report; report date and retrieval timestamp are shown separately.",
        "verified_recent": "Report date is no more than 2 calendar days old.",
        "official_delayed": "Report date is 3–7 calendar days old.",
        "historical": "Report date is more than 7 calendar days old.",
        "source_unavailable": "Last retrieval failed; the prior validated snapshot remains available if one exists.",
    }


def get_latest_daily_report() -> dict[str, Any]:
    snapshot = load_daily_snapshot()
    return {
        "data_status": get_daily_source_status()["status"],
        "is_live": False,
        "report_date": snapshot["report_date"],
        "source_post_published_at": snapshot.get("source_post_published_at"),
        "retrieved_at_utc": snapshot["retrieved_at_utc"],
        "retrieval_timestamp_basis": snapshot["retrieval_timestamp_basis"],
        "source_name": snapshot["source_name"],
        "source_page_url": snapshot["source_page_url"],
        "source_url": snapshot["source_url"],
        "source_sha256": snapshot["source_sha256"],
        "dataset_version": snapshot["dataset_version"],
        "provisional_warning": snapshot["provisional_warning"],
        "daily_district_report_available": snapshot["daily_district_report_available"],
        "reported_district_count": len(snapshot["reported_district_codes"]),
        "expected_district_count": len(EXPECTED_DISTRICT_CODES),
        "statewide_records": snapshot["statewide_records"],
    }


def cumulative_statistics() -> list[dict[str, Any]]:
    snapshot = load_daily_snapshot()
    return [
        {
            "disease": row["disease"],
            "disease_subtype": row.get("disease_subtype"),
            "source_label": row["source_label"],
            "report_date": snapshot["report_date"],
            "metric_period": "Cumulative 2026",
            **row["cumulative_2026"],
            "source_values": row["source_values"]["cumulative_2026"],
            "source_value_status": row["source_value_status"]["cumulative_2026"],
        }
        for row in snapshot["statewide_records"]
    ]


def daily_statistics(period: str) -> list[dict[str, Any]]:
    if period not in {"daily", "present_month"}:
        raise ValueError(f"Unsupported IDSP report period: {period}")
    snapshot = load_daily_snapshot()
    return [
        {
            "disease": row["disease"],
            "disease_subtype": row.get("disease_subtype"),
            "source_label": row["source_label"],
            "report_date": snapshot["report_date"],
            "metric_period": "Daily" if period == "daily" else "Present Month",
            **row[period],
            "source_values": row["source_values"][period],
            "source_value_status": row["source_value_status"][period],
        }
        for row in snapshot["statewide_records"]
    ]


def district_daily_statistics(
    disease: str | None = None,
    disease_subtype: str | None = None,
) -> dict[str, Any]:
    snapshot = load_daily_snapshot()
    rows = [
        row for row in snapshot["district_records"]
        if (disease is None or row["disease"].casefold() == disease.casefold())
        and (
            disease_subtype is None
            or (row.get("disease_subtype") or "").casefold() == disease_subtype.casefold()
        )
    ]
    return {
        "data_status": get_daily_source_status()["status"],
        "report_date": snapshot["report_date"],
        "metric_period": "Daily",
        "temporal_granularity": "district daily report values",
        "district_report_available": snapshot["daily_district_report_available"],
        "expected_district_count": len(EXPECTED_DISTRICT_CODES),
        "reported_district_count": len(snapshot["reported_district_codes"]),
        "reported_district_codes": snapshot["reported_district_codes"],
        "missing_district_codes": sorted(
            set(EXPECTED_DISTRICT_CODES) - set(snapshot["reported_district_codes"])
        ),
        "records": rows,
        "source_url": snapshot["source_url"],
        "note": (
            "District table reports suspected/confirmed cases separately but provides a single "
            "reported deaths field where marked D; deaths are not assigned to a case classification."
        ),
    }


def load_daily_history() -> list[dict[str, Any]]:
    if not SNAPSHOT_DIR.is_dir():
        return []
    by_report_date: dict[str, dict[str, Any]] = {}
    for path in sorted(SNAPSHOT_DIR.glob("*.json")):
        snapshot = _read_json(path)
        try:
            validate_daily_snapshot(snapshot)
        except DailySurveillanceUnavailable:
            continue
        if not snapshot["report_date"].startswith("2026-"):
            continue
        existing = by_report_date.get(snapshot["report_date"])
        if existing is None or snapshot["retrieved_at_utc"] > existing["retrieved_at_utc"]:
            by_report_date[snapshot["report_date"]] = snapshot
    return [by_report_date[key] for key in sorted(by_report_date)]


def load_backfill_status() -> dict[str, Any] | None:
    path = DAILY_DIR / "backfill_2026_status.json"
    return _read_json(path) if path.is_file() else None


def daily_time_series(disease: str) -> dict[str, Any]:
    if disease not in {"Dengue", "Leptospirosis"}:
        raise ValueError(f"Unsupported daily IDSP series disease: {disease}")
    snapshots = load_daily_history()
    records = []
    for snapshot in snapshots:
        row = next(
            (item for item in snapshot["statewide_records"] if item["disease"] == disease),
            None,
        )
        if row is None:
            continue
        records.append({
            "report_date": snapshot["report_date"],
            "disease": disease,
            "source_label": row["source_label"],
            **row["daily"],
            "source_values": row["source_values"]["daily"],
            "source_value_status": row["source_value_status"]["daily"],
            "provisional": True,
            "source_url": snapshot["source_url"],
        })
    if not records:
        raise DailySurveillanceUnavailable(f"No validated 2026 daily IDSP records are available for {disease}.")

    latest = date.fromisoformat(records[-1]["report_date"])
    coverage_start = date.fromisoformat(records[0]["report_date"])
    expected_dates = {
        date.fromordinal(day).isoformat()
        for day in range(coverage_start.toordinal(), latest.toordinal() + 1)
    }
    observed_dates = {row["report_date"] for row in records}
    missing_dates = sorted(expected_dates - observed_dates)
    return {
        "disease": disease,
        "reporting_period_start": records[0]["report_date"],
        "reporting_period_end": records[-1]["report_date"],
        "report_count": len(records),
        "records": records,
        "calendar_dates_in_range": len(expected_dates),
        "missing_report_dates": missing_dates,
        "missing_report_date_count": len(missing_dates),
        "note": (
            "Only dated DHS reports actually discovered and validated are represented. Missing calendar "
            "dates are absent reports, not zero-case observations. Source values remain preliminary."
        ),
    }


def period_summary(
    disease: str,
    *,
    end_date: date,
    days: int,
) -> dict[str, Any]:
    if days not in {7, 30}:
        raise ValueError("IDSP summaries support only 7-day and 30-day windows.")
    series = daily_time_series(disease)
    records_by_date = {row["report_date"]: row for row in series["records"]}
    fields = (
        "suspected_cases",
        "suspected_deaths",
        "confirmed_cases",
        "confirmed_deaths",
    )
    results = {}
    current_start = date.fromordinal(end_date.toordinal() - days + 1)
    previous_end = date.fromordinal(current_start.toordinal() - 1)
    previous_start = date.fromordinal(previous_end.toordinal() - days + 1)
    for field in fields:
        results[field] = {
            "current": _period_field_summary(records_by_date, field, current_start, end_date),
            "previous": _period_field_summary(records_by_date, field, previous_start, previous_end),
        }
        current = results[field]["current"]
        previous = results[field]["previous"]
        if current["complete"] and previous["complete"]:
            current_value = current["reported_total"]
            previous_value = previous["reported_total"]
            difference = current_value - previous_value
            current["comparison"] = {
                "previous_period_total": previous_value,
                "absolute_change": difference,
                "percentage_change": (
                    round(difference / previous_value * 100, 2) if previous_value else None
                ),
                "interpretation": (
                    "Reported total increased compared with the previous equivalent period."
                    if difference > 0 else
                    "Reported total decreased compared with the previous equivalent period."
                    if difference < 0 else
                    "Reported total was unchanged compared with the previous equivalent period."
                ),
            }
        else:
            current["comparison"] = {
                "available": False,
                "reason": "Current and previous periods both require complete report dates and numeric source values.",
            }
    return {
        "disease": disease,
        "window_days": days,
        "current_period_start": current_start.isoformat(),
        "current_period_end": end_date.isoformat(),
        "previous_period_start": previous_start.isoformat(),
        "previous_period_end": previous_end.isoformat(),
        "metrics": results,
        "adequacy_rule": (
            f"Both equivalent windows require {days}/{days} report dates and numeric values for each metric. "
            "A missing report day, source dash, or blank source cell makes that metric's period incomplete."
        ),
        "provisional_warning": "Source-reported daily values are preliminary and may be revised.",
    }


def _period_field_summary(
    records_by_date: dict[str, dict[str, Any]],
    field: str,
    start: date,
    end: date,
) -> dict[str, Any]:
    dates = [
        date.fromordinal(value).isoformat()
        for value in range(start.toordinal(), end.toordinal() + 1)
    ]
    rows = [records_by_date.get(value) for value in dates]
    missing_dates = [value for value, row in zip(dates, rows) if row is None]
    missing_values = [
        value for value, row in zip(dates, rows)
        if row is not None and row.get(field) is None
    ]
    complete = not missing_dates and not missing_values
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "expected_report_dates": len(dates),
        "reports_received": len(dates) - len(missing_dates),
        "missing_report_dates": missing_dates,
        "missing_numeric_value_dates": missing_values,
        "complete": complete,
        "reported_total": sum(row[field] for row in rows if row is not None and row[field] is not None)
        if complete else None,
    }


def record_daily_refresh_failure(message: str, attempted_at: str | None = None) -> None:
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    status = _read_json(STATUS_PATH) if STATUS_PATH.is_file() else {}
    status["last_attempt_status"] = "unavailable"
    status["last_attempt"] = {
        "timestamp_utc": attempted_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "unavailable",
        "error": message[:1000],
        "cached_snapshot_retained": LATEST_PATH.is_file(),
    }
    _atomic_write_json(STATUS_PATH, status)


def record_daily_refresh_success(snapshot: dict[str, Any]) -> None:
    validate_daily_snapshot(snapshot)
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"idsp_{snapshot['report_date']}_{snapshot['dataset_version']}.json"
    archived = SNAPSHOT_DIR / filename
    duplicate_snapshot = archived.is_file()
    if not duplicate_snapshot:
        _atomic_write_json(archived, snapshot)
    if LATEST_PATH.is_file():
        current = _read_json(LATEST_PATH)
        current_date = _valid_report_date(current.get("report_date"))
    else:
        current_date = None
    update_latest = current_date is None or snapshot["report_date"] >= current_date
    if update_latest:
        _atomic_write_json(LATEST_PATH, snapshot)
    status = _read_json(STATUS_PATH) if STATUS_PATH.is_file() else {}
    status.update({
        "last_attempt_status": "success",
        "last_attempt": {
            "timestamp_utc": snapshot["retrieved_at_utc"],
            "status": "success",
            "report_date": snapshot["report_date"],
            "dataset_version": snapshot["dataset_version"],
            "snapshot_file": archived.relative_to(ROOT).as_posix(),
            "cached_snapshot_retained": LATEST_PATH.is_file(),
            "duplicate_snapshot": duplicate_snapshot,
        },
    })
    if update_latest:
        status.update({
            "latest_report_date": snapshot["report_date"],
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
