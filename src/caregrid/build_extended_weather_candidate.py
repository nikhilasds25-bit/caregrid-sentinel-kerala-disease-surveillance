"""Acquire and aggregate separate 2016-2025 weather candidates for Kerala locations."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

from caregrid.integrate_historical_weather import DISTRICT_LOCATIONS

ROOT = Path(__file__).resolve().parents[2]
API_URL = "https://archive-api.open-meteo.com/v1/archive"
API_DOCS = "https://open-meteo.com/en/docs/historical-weather-api"
TIMEZONE = "Asia/Kolkata"
START_DATE = "2016-01-01"
END_DATE = "2025-12-31"
YEARS = tuple(range(2016, 2026))
VARIABLES = (
    "precipitation_sum",
    "temperature_2m_mean",
    "temperature_2m_min",
    "temperature_2m_max",
    "relative_humidity_2m_mean",
    "dew_point_2m_mean",
)
OUTPUT_PATH = (
    ROOT
    / "data"
    / "candidates"
    / "kerala_district_representative_weather_monthly_2016_2025.csv"
)
METADATA_PATH = (
    ROOT
    / "data"
    / "candidates"
    / "kerala_district_representative_weather_monthly_2016_2025.metadata.json"
)
RAW_DIR = ROOT / "data" / "raw" / "open_meteo_weather_2016_2025"
VARIABLE_COLUMNS = {
    "precipitation_sum": "precipitation_sum_mm",
    "temperature_2m_mean": "temperature_2m_mean_c",
    "temperature_2m_min": "temperature_2m_min_c",
    "temperature_2m_max": "temperature_2m_max_c",
    "relative_humidity_2m_mean": "relative_humidity_2m_mean_pct",
    "dew_point_2m_mean": "dew_point_2m_mean_c",
}
EXPECTED_UNITS = {
    "precipitation_sum": "mm",
    "temperature_2m_mean": "°C",
    "temperature_2m_min": "°C",
    "temperature_2m_max": "°C",
    "relative_humidity_2m_mean": "%",
    "dew_point_2m_mean": "°C",
}
SOURCE_DISTRICT_NAMES = {
    "Thiruvananthapuram": "Thiruvananthapuram",
    "Kollam": "Kollam",
    "Pathanamthitta": "Pathanamthitta",
    "Alappuzha": "Alappuzha",
    "Kottayam": "Kottayam",
    "Idukki (Painavu)": "Idukki",
    "Ernakulam (Kochi)": "Ernakulam",
    "Thrissur": "Thrissur",
    "Palakkad": "Palakkad",
    "Malappuram": "Malappuram",
    "Kozhikode": "Kozhikode",
    "Wayanad (Kalpetta)": "Wayanad",
    "Kannur": "Kannur",
    "Kasaragod": "Kasaragod",
}
BATCH_RAW_PATH = RAW_DIR / "district_locations_batch_2016_2025.json"


class ExtendedWeatherError(ValueError):
    """Raised when a cached or returned weather response is structurally invalid."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _batch_params() -> dict[str, str]:
    return {
        "latitude": ",".join(str(latitude) for _, latitude, _ in DISTRICT_LOCATIONS),
        "longitude": ",".join(str(longitude) for _, _, longitude in DISTRICT_LOCATIONS),
        "start_date": START_DATE,
        "end_date": END_DATE,
        "daily": ",".join(VARIABLES),
        "timezone": TIMEZONE,
    }


def _fetch_batch(refresh: bool) -> dict[str, Any]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    params = _batch_params()
    if BATCH_RAW_PATH.exists() and not refresh:
        envelope = json.loads(BATCH_RAW_PATH.read_text(encoding="utf-8"))
        if envelope.get("request", {}).get("params") != params:
            raise ExtendedWeatherError("cached multi-location request parameters do not match")
        body = envelope.get("response_body")
        if not isinstance(body, str):
            raise ExtendedWeatherError("cached multi-location response body is missing")
        if hashlib.sha256(body.encode("utf-8")).hexdigest() != envelope.get(
            "response_body_sha256"
        ):
            raise ExtendedWeatherError("cached multi-location response body hash mismatch")
        return envelope

    last_error = "unknown weather acquisition failure"
    for attempt in range(4):
        try:
            response = requests.get(API_URL, params=params, timeout=(15, 180))
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_seconds = (
                    min(120, max(1, int(retry_after)))
                    if retry_after and retry_after.isdigit()
                    else min(120, 15 * (2**attempt))
                )
                last_error = f"HTTP 429 rate limited; retrying after {wait_seconds}s"
                if attempt < 3:
                    time.sleep(wait_seconds)
                    continue
                break
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list) or len(payload) != len(DISTRICT_LOCATIONS):
                raise ExtendedWeatherError(
                    "multi-location response did not contain one object per requested location"
                )
            body = response.text
            envelope = {
                "source": "Open-Meteo Historical Weather API",
                "endpoint": API_URL,
                "documentation_url": API_DOCS,
                "retrieved_at_utc": _utc_now(),
                "request": {"url": response.url, "params": params},
                "response_status": response.status_code,
                "response_headers": {
                    key: value
                    for key, value in response.headers.items()
                    if key.lower() in {"content-type", "date", "last-modified", "etag"}
                },
                "response_body_sha256": hashlib.sha256(
                    body.encode("utf-8")
                ).hexdigest(),
                "response_body": body,
            }
            BATCH_RAW_PATH.write_text(
                json.dumps(envelope, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return envelope
        except (
            requests.RequestException,
            json.JSONDecodeError,
            ExtendedWeatherError,
            OSError,
        ) as exc:
            last_error = str(exc)
            if attempt < 3:
                time.sleep(2**attempt)
    raise ExtendedWeatherError(f"Open-Meteo multi-location request failed: {last_error}")


def _validate_payload(
    payload: dict[str, Any],
    district_location: str,
    latitude: float,
    longitude: float,
) -> None:
    if not isinstance(payload.get("daily"), dict):
        raise ExtendedWeatherError(f"{district_location}: response has no daily object")
    if payload.get("timezone") != TIMEZONE:
        raise ExtendedWeatherError(f"{district_location}: unexpected response timezone")
    daily = payload["daily"]
    dates = daily.get("time")
    if not isinstance(dates, list):
        raise ExtendedWeatherError(f"{district_location}: response has no daily time array")
    parsed_dates = pd.to_datetime(dates, format="%Y-%m-%d", errors="coerce")
    if parsed_dates.isna().any() or parsed_dates.duplicated().any():
        raise ExtendedWeatherError(f"{district_location}: invalid or duplicate weather dates")
    if not parsed_dates.is_monotonic_increasing:
        raise ExtendedWeatherError(f"{district_location}: weather dates are not ordered")
    if (
        len(parsed_dates)
        and (
            parsed_dates.min() < pd.Timestamp(START_DATE)
            or parsed_dates.max() > pd.Timestamp(END_DATE)
        )
    ):
        raise ExtendedWeatherError(
            f"{district_location}: returned dates fall outside requested range "
            f"{START_DATE} through {END_DATE}"
        )
    units = payload.get("daily_units")
    if not isinstance(units, dict):
        raise ExtendedWeatherError(f"{district_location}: response has no daily_units")
    for variable in VARIABLES:
        values = daily.get(variable)
        if values is None:
            continue
        if units.get(variable) != EXPECTED_UNITS[variable]:
            raise ExtendedWeatherError(
                f"{district_location}: unexpected unit for {variable}: {units.get(variable)!r}"
            )
        if not isinstance(values, list) or len(values) != len(parsed_dates):
            raise ExtendedWeatherError(
                f"{district_location}: invalid {variable} daily array length"
            )
        for value in values:
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ExtendedWeatherError(
                    f"{district_location}: nonnumeric {variable} value"
                )
            if not math.isfinite(value):
                raise ExtendedWeatherError(
                    f"{district_location}: non-finite {variable} value"
                )
            if variable == "precipitation_sum" and value < 0:
                raise ExtendedWeatherError(
                    f"{district_location}: negative precipitation value"
                )
            if variable == "relative_humidity_2m_mean" and not 0 <= value <= 100:
                raise ExtendedWeatherError(
                    f"{district_location}: humidity outside 0-100 percent"
                )
    if (payload.get("latitude") is None) or (payload.get("longitude") is None):
        raise ExtendedWeatherError(
            f"{district_location}: response omitted returned coordinates"
        )
    if abs(float(payload["latitude"]) - latitude) > 0.1 or abs(
        float(payload["longitude"]) - longitude
    ) > 0.1:
        raise ExtendedWeatherError(
            f"{district_location}: returned coordinate is inconsistent with request"
        )


def _daily_frame(
    envelope: dict[str, Any],
    district_location: str,
    district: str,
    latitude: float,
    longitude: float,
) -> pd.DataFrame:
    payload = json.loads(envelope["response_body"])
    daily = payload["daily"]
    frame = pd.DataFrame({"date": pd.to_datetime(daily["time"])})
    for variable, column in VARIABLE_COLUMNS.items():
        values = daily.get(variable)
        if values is None:
            frame[column] = np.nan
            continue
        frame[column] = pd.to_numeric(
            pd.Series(values), errors="coerce"
        ).to_numpy(dtype=float)
    frame["district_location"] = district_location
    frame["district"] = district
    frame["latitude"] = latitude
    frame["longitude"] = longitude
    frame["returned_latitude"] = payload["latitude"]
    frame["returned_longitude"] = payload["longitude"]
    frame["elevation_m"] = payload.get("elevation")
    return frame


def _missing_daily_frame(
    district_location: str,
    district: str,
    latitude: float,
    longitude: float,
) -> pd.DataFrame:
    frame = pd.DataFrame({"date": pd.Series([], dtype="datetime64[ns]")})
    for column in VARIABLE_COLUMNS.values():
        frame[column] = pd.Series([], dtype=float)
    frame["district_location"] = pd.Series([], dtype=str)
    frame["district"] = pd.Series([], dtype=str)
    frame["latitude"] = pd.Series([], dtype=float)
    frame["longitude"] = pd.Series([], dtype=float)
    frame["returned_latitude"] = pd.Series([], dtype=float)
    frame["returned_longitude"] = pd.Series([], dtype=float)
    frame["elevation_m"] = pd.Series([], dtype=float)
    return frame


def aggregate_monthly_weather(daily: pd.DataFrame) -> pd.DataFrame:
    """Aggregate observed daily values; never turn missing days into zeros."""
    locations = {
        (name, lat, lon): SOURCE_DISTRICT_NAMES[name]
        for name, lat, lon in DISTRICT_LOCATIONS
    }
    if daily.duplicated(["date", "district_location"]).any():
        raise ExtendedWeatherError("daily weather has duplicate date/location keys")
    records: list[dict[str, Any]] = []
    for (district_location, latitude, longitude), district in locations.items():
        location_data = daily[daily["district_location"].eq(district_location)].copy()
        if location_data.empty:
            location_data = _missing_daily_frame(
                district_location, district, latitude, longitude
            )
        for column in ("returned_latitude", "returned_longitude", "elevation_m"):
            if column not in location_data:
                location_data[column] = np.nan
        if location_data["date"].duplicated().any():
            raise ExtendedWeatherError(
                f"{district_location}: duplicate dates in daily weather"
            )
        location_data["period"] = location_data["date"].dt.strftime("%Y-%m")
        for year in YEARS:
            for month_num in range(1, 13):
                period = f"{year}-{month_num:02d}"
                group = location_data[location_data["period"].eq(period)]
                days_expected = len(pd.date_range(
                    f"{period}-01", pd.Period(period).end_time.normalize(), freq="D"
                ))
                row: dict[str, Any] = {
                    "year": year,
                    "month_num": month_num,
                    "period": period,
                    "district": district,
                    "district_location": district_location,
                    "latitude": latitude,
                    "longitude": longitude,
                    "returned_latitude": (
                        group["returned_latitude"].dropna().iloc[0]
                        if group["returned_latitude"].notna().any()
                        else None
                    ),
                    "returned_longitude": (
                        group["returned_longitude"].dropna().iloc[0]
                        if group["returned_longitude"].notna().any()
                        else None
                    ),
                    "elevation_m": (
                        group["elevation_m"].dropna().iloc[0]
                        if group["elevation_m"].notna().any()
                        else None
                    ),
                    "days_expected": days_expected,
                    "daily_rows_returned": int(
                        group[list(VARIABLE_COLUMNS.values())].notna().any(axis=1).sum()
                    ),
                }
                for source_variable, column in VARIABLE_COLUMNS.items():
                    observed = group[column].dropna()
                    observed_days = int(observed.size)
                    row[f"{column}_observed_days"] = observed_days
                    row[f"{column}_missing_days"] = days_expected - observed_days
                    if source_variable == "precipitation_sum":
                        row["precipitation_observed_sum_mm"] = (
                            float(observed.sum()) if observed_days else None
                        )
                        row["precipitation_sum_mm"] = (
                            float(observed.sum())
                            if observed_days == days_expected
                            else None
                        )
                    else:
                        row[column] = float(observed.mean()) if observed_days else None
                complete = all(
                    row[f"{column}_observed_days"] == days_expected
                    for column in VARIABLE_COLUMNS.values()
                )
                row["weather_availability_status"] = (
                    "complete_month" if complete
                    else "partial_month" if row["daily_rows_returned"] > 0
                    else "unavailable"
                )
                row["precipitation_aggregation"] = (
                    "sum_of_daily_precipitation; published monthly total only when "
                    "all expected days are present"
                )
                row["other_variable_aggregation"] = (
                    "mean_of_available_daily_values; observed and missing day counts retained"
                )
                row["spatial_scope"] = (
                    "single representative coordinate; not a measured district-wide average"
                )
                records.append(row)
    result = pd.DataFrame.from_records(records)
    natural_key = ["period", "district"]
    if result.duplicated(natural_key).any():
        raise ExtendedWeatherError("monthly weather has duplicate district-month keys")
    return result.sort_values(["period", "district"], kind="stable").reset_index(drop=True)


def build_weather_candidate(refresh: bool = False) -> tuple[pd.DataFrame, dict[str, Any]]:
    batch = _fetch_batch(refresh)
    batch_payload = json.loads(batch["response_body"])
    daily_frames: list[pd.DataFrame] = []
    location_metadata: list[dict[str, Any]] = []
    for index, (district_location, latitude, longitude) in enumerate(DISTRICT_LOCATIONS):
        payload = batch_payload[index]
        district = SOURCE_DISTRICT_NAMES[district_location]
        try:
            _validate_payload(payload, district_location, latitude, longitude)
        except ExtendedWeatherError as exc:
            daily_frames.append(
                _missing_daily_frame(
                    district_location, district, latitude, longitude
                )
            )
            location_metadata.append({
                "district": district,
                "district_location": district_location,
                "requested_latitude": latitude,
                "requested_longitude": longitude,
                "retrieval_status": "failed",
                "error": str(exc),
                "batch_response_sha256": batch["response_body_sha256"],
            })
            continue
        location_body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        location_hash = hashlib.sha256(location_body.encode("utf-8")).hexdigest()
        location_envelope = {
            "response_body": location_body,
            "retrieved_at_utc": batch["retrieved_at_utc"],
        }
        daily_frames.append(
            _daily_frame(
                location_envelope, district_location, district, latitude, longitude
            )
        )
        location_metadata.append({
            "district": district,
            "district_location": district_location,
            "requested_latitude": latitude,
            "requested_longitude": longitude,
            "returned_latitude": payload.get("latitude"),
            "returned_longitude": payload.get("longitude"),
            "elevation_m": payload.get("elevation"),
            "timezone": payload.get("timezone"),
            "daily_units": payload.get("daily_units"),
            "response_date": batch.get("response_headers", {}).get("Date"),
            "etag": batch.get("response_headers", {}).get("ETag"),
            "last_modified": batch.get("response_headers", {}).get("Last-Modified"),
            "response_body_sha256": location_hash,
            "batch_response_sha256": batch.get("response_body_sha256"),
            "retrieved_at_utc": batch.get("retrieved_at_utc"),
            "response_status": batch.get("response_status"),
            "response_root_metadata": {
                key: payload.get(key)
                for key in (
                    "generationtime_ms",
                    "utc_offset_seconds",
                    "timezone_abbreviation",
                )
            },
            "model_metadata_status": (
                "No explicit model/reanalysis identifier was exposed in the captured "
                "archive response."
            ),
            "retrieval_status": "success",
        })
    daily = pd.concat(daily_frames, ignore_index=True)
    monthly = aggregate_monthly_weather(daily)
    source_hashes = {
        item["district_location"]: item.get("response_body_sha256")
        for item in location_metadata
    }
    metadata = {
        "source_name": "Open-Meteo Historical Weather API",
        "source_url": API_URL,
        "documentation_url": API_DOCS,
        "retrieved_at_utc": _utc_now(),
        "start_date": START_DATE,
        "end_date": END_DATE,
        "timezone": TIMEZONE,
        "requested_variables": list(VARIABLES),
        "expected_units": EXPECTED_UNITS,
        "requested_model": None,
        "model_metadata_status": (
            "The API response did not expose an explicit model/reanalysis identifier; "
            "no model name is inferred."
        ),
        "aggregation_methods": {
            "precipitation_sum_mm": (
                "sum daily precipitation; full-month value is null unless all expected "
                "daily values are present; partial observed sum is retained separately"
            ),
            "temperature_2m_mean_c": "arithmetic mean of available daily means",
            "temperature_2m_min_c": "arithmetic mean of available daily minima",
            "temperature_2m_max_c": "arithmetic mean of available daily maxima",
            "relative_humidity_2m_mean_pct": "arithmetic mean of available daily means",
            "dew_point_2m_mean_c": "arithmetic mean of available daily means",
        },
        "spatial_scope": (
            "One representative coordinate per district; not a measured or areal "
            "district-wide average."
        ),
        "raw_response_directory": str(RAW_DIR.relative_to(ROOT).as_posix()),
        "raw_batch_snapshot": str(BATCH_RAW_PATH.relative_to(ROOT).as_posix()),
        "batch_response_sha256": batch["response_body_sha256"],
        "response_date": batch.get("response_headers", {}).get("Date"),
        "etag": batch.get("response_headers", {}).get("ETag"),
        "location_responses": location_metadata,
        "source_response_hashes": source_hashes,
        "monthly_records": len(monthly),
        "monthly_complete_records": int(
            monthly["weather_availability_status"].eq("complete_month").sum()
        ),
        "monthly_partial_records": int(
            monthly["weather_availability_status"].eq("partial_month").sum()
        ),
        "monthly_unavailable_records": int(
            monthly["weather_availability_status"].eq("unavailable").sum()
        ),
    }
    return monthly, metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--metadata", type=Path, default=METADATA_PATH)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    existing = [str(path) for path in (args.output, args.metadata) if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(
            "Refusing to overwrite existing outputs: " + ", ".join(existing)
            + "; pass --overwrite only after reviewing them."
        )
    monthly, metadata = build_weather_candidate(refresh=args.refresh)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    csv_bytes = monthly.to_csv(index=False).encode("utf-8")
    args.output.write_bytes(csv_bytes)
    metadata["candidate_csv_path"] = str(args.output)
    metadata["candidate_csv_sha256"] = hashlib.sha256(csv_bytes).hexdigest()
    metadata["feature_missing_value_counts"] = {
        column: int(monthly[column].isna().sum())
        for column in VARIABLE_COLUMNS.values()
    }
    args.metadata.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(monthly)} district-month rows; "
        f"complete={metadata['monthly_complete_records']}, "
        f"partial={metadata['monthly_partial_records']}, "
        f"unavailable={metadata['monthly_unavailable_records']}"
    )


if __name__ == "__main__":
    main()
