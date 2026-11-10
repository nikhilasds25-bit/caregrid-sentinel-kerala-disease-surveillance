"""Acquire Open-Meteo historical weather and join it to statewide monthly disease data."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
DISEASE_CSV = ROOT / "data" / "processed" / "kerala_disease_monthly_2021_2024.csv"
RAW_DIR = ROOT / "data" / "raw" / "open_meteo_weather"
WEATHER_CSV = ROOT / "data" / "processed" / "kerala_weather_monthly_district_proxy_2021_2024.csv"
INTEGRATED_CSV = ROOT / "data" / "processed" / "kerala_disease_weather_monthly_2021_2024.csv"
QUALITY_REPORT = ROOT / "reports" / "weather_data_quality_report.md"
READINESS_REPORT = ROOT / "reports" / "analysis_data_readiness.md"
FIGURE_DIR = ROOT / "reports" / "figures"
API_URL = "https://archive-api.open-meteo.com/v1/archive"
API_DOCS = "https://open-meteo.com/en/docs/historical-weather-api"
TIMEZONE = "Asia/Kolkata"
DAILY_VARIABLES = (
    "precipitation_sum",
    "temperature_2m_mean",
    "temperature_2m_min",
    "temperature_2m_max",
)
WEATHER_COLUMNS = {
    "precipitation_sum": "precipitation_sum_mm",
    "temperature_2m_mean": "temperature_2m_mean_c",
    "temperature_2m_min": "temperature_2m_min_c",
    "temperature_2m_max": "temperature_2m_max_c",
}
EXPECTED_UNITS = {
    "precipitation_sum": "mm",
    "temperature_2m_mean": "°C",
    "temperature_2m_min": "°C",
    "temperature_2m_max": "°C",
}
REQUIRED_DISEASE_COLUMNS = {
    "period",
    "year",
    "month_num",
    "geography",
    "geography_level",
    "disease",
    "classification",
    "classification_note",
    "cases",
    "deaths",
    "source_file",
    "source_url",
}
EXPECTED_CLASSIFICATION_BY_YEAR = {
    2021: "reported_category_status_not_split",
    2022: "non_probable_category_probable_separate",
    2023: "Confirmed",
    2024: "Confirmed",
}

# Approximate district-headquarters locations; these are spatial representatives,
# not population-weighted centroids or official district weather stations.
DISTRICT_LOCATIONS = (
    ("Thiruvananthapuram", 8.5241, 76.9366),
    ("Kollam", 8.8932, 76.6141),
    ("Pathanamthitta", 9.2648, 76.7870),
    ("Alappuzha", 9.4981, 76.3388),
    ("Kottayam", 9.5916, 76.5222),
    ("Idukki (Painavu)", 9.8494, 76.9720),
    ("Ernakulam (Kochi)", 9.9816, 76.2999),
    ("Thrissur", 10.5276, 76.2144),
    ("Palakkad", 10.7867, 76.6548),
    ("Malappuram", 11.0510, 76.0711),
    ("Kozhikode", 11.2588, 75.7804),
    ("Wayanad (Kalpetta)", 11.6085, 76.0820),
    ("Kannur", 11.8745, 75.3704),
    ("Kasaragod", 12.4996, 74.9869),
)


class PipelineError(ValueError):
    """Expected input, API, or validation failure with a concise user-facing reason."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(str(value).replace("|", "\\|").replace("\n", " ") for value in row)
            + " |"
        )
    return "\n".join(lines)


def _write_quality_report(checks: list[tuple[str, str, str]], failure: str | None = None) -> None:
    lines = [
        "# Historical weather data-quality report",
        "",
        f"- Run timestamp (UTC): {_utc_now()}",
        f"- Disease input: `{DISEASE_CSV.relative_to(ROOT).as_posix()}`",
        f"- Weather API: [Open-Meteo Historical Weather API]({API_URL})",
        f"- API documentation: [Historical Weather API documentation]({API_DOCS})",
        "- Requested daily variables: `precipitation_sum` (mm), "
        "`temperature_2m_mean`, `temperature_2m_min`, `temperature_2m_max` (°C).",
        "- API timezone: `Asia/Kolkata`; the returned daily date is used as the local calendar date.",
        "- Weather aggregation: monthly precipitation is each location's daily precipitation "
        "summed over the month, then averaged equally over the 14 representative locations. "
        "Monthly temperature metrics are calculated at each location, then averaged equally "
        "over those locations.",
        "- The equal-weight location mean is a **statewide proxy**, not an official "
        "population-weighted statewide weather measurement.",
        "",
        "## Representative location coordinates",
        "",
        _markdown_table(
            ["District representative", "Latitude", "Longitude"],
            [[name, f"{lat:.4f}", f"{lon:.4f}"] for name, lat, lon in DISTRICT_LOCATIONS],
        ),
        "",
        "These approximate headquarters points are spatial representatives, not official weather "
        "stations, population-weighted centroids, or complete district-area averages.",
        "",
        "## Validation results",
        "",
        _markdown_table(
            ["Check", "Result", "Details"],
            [[name, status, detail] for name, status, detail in checks],
        ),
    ]
    if failure:
        lines.extend(["", "## Outcome", "", f"**Pipeline stopped:** {failure}"])
    else:
        lines.extend([
            "",
            "## Caveats",
            "",
            "- The API chooses its applicable historical reanalysis/model automatically; "
            "the model is not pinned in this script. The full response and retrieval metadata "
            "are retained in `data/raw/open_meteo_weather/` for provenance.",
            "- API values and source data are preserved; no missing observations are replaced "
            "with zero or interpolated.",
        ])
    QUALITY_REPORT.parent.mkdir(parents=True, exist_ok=True)
    QUALITY_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_disease(checks: list[tuple[str, str, str]]) -> pd.DataFrame:
    if not DISEASE_CSV.is_file():
        raise PipelineError(f"Required statewide monthly disease file is missing: {DISEASE_CSV}")
    try:
        data = pd.read_csv(DISEASE_CSV)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise PipelineError(f"Could not read statewide monthly disease data: {exc}") from exc

    missing_columns = sorted(REQUIRED_DISEASE_COLUMNS - set(data.columns))
    if missing_columns:
        raise PipelineError(f"Disease input is missing required columns: {missing_columns}")
    if data.empty:
        raise PipelineError("Statewide monthly disease input contains no records.")
    if data[list(REQUIRED_DISEASE_COLUMNS)].isna().any().any():
        raise PipelineError("Disease input has missing values in required fields; no rows were filled.")
    if set(data["geography"].astype(str)) != {"Kerala"}:
        raise PipelineError("Disease input is not exclusively Kerala statewide data.")
    if set(data["geography_level"].astype(str)) != {"Statewide"}:
        raise PipelineError("Disease input contains non-statewide geography; refusing a statewide join.")
    if data["classification"].astype(str).str.strip().eq("").any():
        raise PipelineError("Disease classification contains blank labels.")
    if set(data["disease"].astype(str)) != {"Dengue", "Leptospirosis"}:
        raise PipelineError("Disease input does not contain exactly Dengue and Leptospirosis.")
    if data.duplicated(["period", "geography", "disease", "classification"]).any():
        raise PipelineError("Duplicate disease natural keys detected.")
    cases = pd.to_numeric(data["cases"], errors="coerce")
    deaths = pd.to_numeric(data["deaths"], errors="coerce")
    if cases.isna().any() or deaths.isna().any():
        raise PipelineError("Disease cases/deaths contain non-numeric values.")
    if (cases < 0).any() or (deaths < 0).any():
        raise PipelineError("Disease cases/deaths contain negative values.")

    parsed = pd.to_datetime(data["period"].astype(str) + "-01", format="%Y-%m-%d", errors="coerce")
    years = pd.to_numeric(data["year"], errors="coerce")
    months = pd.to_numeric(data["month_num"], errors="coerce")
    if parsed.isna().any() or not (parsed.dt.year == years).all() or not (
        parsed.dt.month == months
    ).all():
        raise PipelineError("Disease period, year, and month_num fields are inconsistent.")
    data = data.copy()
    data["period_start"] = parsed
    data["cases"] = cases
    data["deaths"] = deaths

    observed_periods = sorted(data["period"].astype(str).unique())
    expected_periods = pd.period_range(parsed.min(), parsed.max(), freq="M").astype(str).tolist()
    missing_periods = sorted(set(expected_periods) - set(observed_periods))
    if missing_periods:
        raise PipelineError(
            "Disease reporting has missing statewide months; they will not be filled: "
            + ", ".join(missing_periods)
        )
    expected_pairs = len(observed_periods) * 2
    observed_pairs = data[["period", "disease"]].drop_duplicates()
    if len(observed_pairs) != expected_pairs or not data.groupby(
        ["period", "disease"], dropna=False
    ).size().eq(1).all():
        raise PipelineError(
            "Disease series does not contain exactly one source row per month and disease; "
            "missing records are not manufactured."
        )
    observed_years = sorted(pd.to_numeric(data["year"], errors="raise").astype(int).unique())
    if any(year not in EXPECTED_CLASSIFICATION_BY_YEAR for year in observed_years):
        raise PipelineError(f"Unexpected disease reporting year(s): {observed_years}")
    for year in observed_years:
        labels = set(data.loc[data["year"] == year, "classification"].astype(str))
        expected_label = EXPECTED_CLASSIFICATION_BY_YEAR[year]
        if labels != {expected_label}:
            raise PipelineError(
                f"Classification for {year} differs from source documentation: "
                f"found {sorted(labels)}, expected {expected_label!r}."
            )
    data["year"] = pd.to_numeric(data["year"], errors="raise").astype(int)
    checks.extend([
        ("Disease schema and statewide scope", "PASS",
         f"{len(data)} source rows; Kerala/Statewide; source classifications retained."),
        ("Disease natural keys and disease coverage", "PASS",
         f"No duplicate period/geography/disease/classification keys; each of "
         f"{len(observed_periods)} months has one row for each of two diseases."),
        ("Disease numeric values", "PASS", "Cases and deaths are numeric and nonnegative."),
        ("Disease month coverage/alignment", "PASS",
         f"{observed_periods[0]} through {observed_periods[-1]}; no missing reporting months."),
        ("Disease classification consistency", "PASS",
         "Verified against source documentation without harmonization: " + "; ".join(
             f"{year}: {EXPECTED_CLASSIFICATION_BY_YEAR[year]}" for year in observed_years
         )),
    ])
    return data.sort_values(
        ["period_start", "disease", "classification"], kind="stable"
    ).reset_index(drop=True)


def _params(latitude: float, longitude: float, start_date: str, end_date: str) -> dict[str, str]:
    return {
        "latitude": str(latitude),
        "longitude": str(longitude),
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": TIMEZONE,
    }


def _read_or_fetch(
    session: requests.Session,
    district: str,
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    refresh: bool,
) -> dict[str, Any]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    filename = district.lower().replace(" ", "_").replace("(", "").replace(")", "") + ".json"
    path = RAW_DIR / filename
    params = _params(latitude, longitude, start_date, end_date)

    if path.is_file() and not refresh:
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            if envelope.get("request", {}).get("params") != params:
                raise PipelineError(f"Cached weather request parameters do not match {district}: {path}")
            if envelope.get("response_body") is None:
                raise PipelineError(f"Cached weather response is missing its body: {path}")
            return envelope
        except (OSError, json.JSONDecodeError) as exc:
            raise PipelineError(f"Could not read cached raw weather response {path}: {exc}") from exc

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = session.get(API_URL, params=params, timeout=(15, 90))
            response.raise_for_status()
            body = response.text
            payload = json.loads(body)
            envelope = {
                "source": "Open-Meteo Historical Weather API",
                "endpoint": API_URL,
                "retrieved_at_utc": _utc_now(),
                "request": {"url": response.url, "params": params},
                "response_status": response.status_code,
                "response_headers": {
                    key: value
                    for key, value in response.headers.items()
                    if key.lower() in {"content-type", "date", "last-modified", "etag"}
                },
                "response_body": body,
            }
            if not isinstance(payload, dict):
                raise PipelineError(f"Unexpected top-level API response for {district}: expected JSON object.")
            path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return envelope
        except (requests.RequestException, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2**attempt)
    raise PipelineError(f"Weather request failed for {district} after 3 attempts: {last_error}")


def _validate_weather_response(
    district: str,
    latitude: float,
    longitude: float,
    envelope: dict[str, Any],
    expected_dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    try:
        payload = json.loads(envelope["response_body"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise PipelineError(f"Raw response body is invalid for {district}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("daily"), dict):
        raise PipelineError(f"Unexpected API response structure for {district}; daily object is required.")
    if payload.get("timezone") != TIMEZONE:
        raise PipelineError(
            f"Unexpected response timezone for {district}: {payload.get('timezone')!r}."
        )
    units = payload.get("daily_units")
    daily = payload["daily"]
    if not isinstance(units, dict):
        raise PipelineError(f"Missing daily_units in weather response for {district}.")
    for variable, expected_unit in EXPECTED_UNITS.items():
        unit = units.get(variable)
        if unit != expected_unit:
            raise PipelineError(
                f"Unexpected unit for {district}.{variable}: {unit!r}; expected {expected_unit!r}."
            )
        if variable not in daily:
            raise PipelineError(f"Weather response for {district} is missing {variable}.")

    raw_dates = daily.get("time")
    if not isinstance(raw_dates, list):
        raise PipelineError(f"Weather response for {district} has no daily time array.")
    parsed_dates = pd.to_datetime(raw_dates, format="%Y-%m-%d", errors="coerce")
    if parsed_dates.isna().any() or parsed_dates.duplicated().any():
        raise PipelineError(f"Weather dates are invalid or duplicated for {district}.")
    if not parsed_dates.equals(pd.DatetimeIndex(expected_dates)):
        missing = sorted(set(expected_dates) - set(parsed_dates))
        extra = sorted(set(parsed_dates) - set(expected_dates))
        raise PipelineError(
            f"Weather date coverage differs for {district}; missing={len(missing)}, extra={len(extra)}."
        )

    result: dict[str, Any] = {
        "date": parsed_dates,
        "district_location": district,
        "requested_latitude": latitude,
        "requested_longitude": longitude,
        "returned_latitude": payload.get("latitude"),
        "returned_longitude": payload.get("longitude"),
        "elevation_m": payload.get("elevation"),
    }
    for variable in DAILY_VARIABLES:
        values = daily[variable]
        if not isinstance(values, list) or len(values) != len(parsed_dates):
            raise PipelineError(f"Unexpected {variable} array length for {district}.")
        numeric = pd.to_numeric(pd.Series(values), errors="coerce")
        if numeric.isna().any() or not np.isfinite(numeric.to_numpy(dtype=float)).all():
            raise PipelineError(f"Missing or non-finite {variable} values for {district}; no imputation applied.")
        if variable == "precipitation_sum" and (numeric < 0).any():
            raise PipelineError(f"Negative precipitation reported for {district}.")
        if variable.startswith("temperature_2m") and ((numeric < -90) | (numeric > 65)).any():
            raise PipelineError(f"Physically implausible temperature reported for {district}.")
        result[WEATHER_COLUMNS[variable]] = numeric.to_numpy(dtype=float)

    frame = pd.DataFrame(result)
    if ((frame["temperature_2m_min_c"] > frame["temperature_2m_mean_c"])
            | (frame["temperature_2m_mean_c"] > frame["temperature_2m_max_c"])).any():
        raise PipelineError(f"Minimum/mean/maximum temperatures are inconsistent for {district}.")
    return frame


def _acquire_weather(
    start_date: str,
    end_date: str,
    refresh: bool,
    checks: list[tuple[str, str, str]],
) -> pd.DataFrame:
    expected_dates = pd.date_range(start_date, end_date, freq="D")
    session = requests.Session()
    frames: list[pd.DataFrame] = []
    errors: list[str] = []
    for district, latitude, longitude in DISTRICT_LOCATIONS:
        try:
            envelope = _read_or_fetch(
                session, district, latitude, longitude, start_date, end_date, refresh
            )
            frame = _validate_weather_response(
                district, latitude, longitude, envelope, expected_dates
            )
            frame["period"] = frame["date"].dt.strftime("%Y-%m")
            frames.append(frame)
            print(f"Weather response validated: {district} ({len(frame)} daily dates)")
        except (PipelineError, requests.RequestException, OSError, json.JSONDecodeError) as exc:
            errors.append(f"{district}: {exc}")
    if errors:
        checks.append(("Weather acquisition and response validation", "FAIL", "; ".join(errors)))
        raise PipelineError("One or more representative-location weather responses failed validation.")
    if len(frames) != len(DISTRICT_LOCATIONS):
        raise PipelineError("Weather coverage is incomplete across representative district locations.")
    daily = pd.concat(frames, ignore_index=True)
    if daily.duplicated(["date", "district_location"]).any():
        raise PipelineError("Duplicate date/location weather keys found.")
    checks.extend([
        ("Weather acquisition and response validation", "PASS",
         f"{len(frames)} raw responses; {len(daily)} daily location records; "
         f"{start_date} through {end_date}; no missing daily values."),
        ("Weather date/location keys", "PASS",
         f"No duplicate date/location keys; each of {len(DISTRICT_LOCATIONS)} locations "
         f"has {len(expected_dates)} distinct daily dates."),
        ("Weather units and physical checks", "PASS",
         "API units match mm and °C; precipitation is nonnegative; temperatures are finite, "
         "within -90 to 65 °C, and min ≤ mean ≤ max."),
    ])
    return daily


def _monthly_weather(daily: pd.DataFrame) -> pd.DataFrame:
    location_month = (
        daily.groupby(["period", "district_location"], as_index=False, sort=True)
        .agg(
            precipitation_sum_mm=("precipitation_sum_mm", "sum"),
            temperature_2m_mean_c=("temperature_2m_mean_c", "mean"),
            temperature_2m_min_c=("temperature_2m_min_c", "mean"),
            temperature_2m_max_c=("temperature_2m_max_c", "mean"),
            days_observed=("date", "nunique"),
        )
    )
    monthly = (
        location_month.groupby("period", as_index=False, sort=True)
        .agg(
            precipitation_sum_mm=("precipitation_sum_mm", "mean"),
            temperature_2m_mean_c=("temperature_2m_mean_c", "mean"),
            temperature_2m_min_c=("temperature_2m_min_c", "mean"),
            temperature_2m_max_c=("temperature_2m_max_c", "mean"),
            weather_location_count=("district_location", "nunique"),
            weather_days_in_month=("days_observed", "min"),
        )
    )
    monthly["aggregation_method"] = "equal_weight_mean_of_14_district_representative_locations"
    monthly["weather_scope"] = "Kerala statewide proxy; not population weighted"
    return monthly


def _association_rows(data: pd.DataFrame) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for (disease, classification), group in data.groupby(
        ["disease", "classification"], sort=True, dropna=False
    ):
        for label, weather_column in (
            ("monthly precipitation (mm)", "precipitation_sum_mm"),
            ("monthly mean temperature (°C)", "temperature_2m_mean_c"),
        ):
            pair = group[["cases", weather_column]].dropna()
            correlation: str = "not estimable"
            if len(pair) >= 3 and pair["cases"].nunique() > 1 and pair[weather_column].nunique() > 1:
                correlation = f"{pair['cases'].corr(pair[weather_column]):.3f}"
            rows.append([
                disease,
                classification,
                label,
                len(pair),
                correlation,
                "descriptive Pearson correlation only; not causal",
            ])
    return rows


def _write_charts(data: pd.DataFrame, monthly_weather: pd.DataFrame) -> list[str]:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    trend_path = FIGURE_DIR / "statewide_monthly_disease_trends_2021_2024.png"
    weather_path = FIGURE_DIR / "kerala_monthly_weather_proxy_2021_2024.png"
    assoc_path = FIGURE_DIR / "disease_weather_descriptive_associations_2021_2024.png"

    fig, axes = plt.subplots(2, 1, figsize=(13, 9), sharex=True)
    for axis, disease in zip(axes, ("Dengue", "Leptospirosis")):
        subset = data[data["disease"] == disease]
        for classification, group in subset.groupby("classification", sort=False):
            axis.plot(
                pd.to_datetime(group["period"].astype(str) + "-01", format="%Y-%m-%d"),
                group["cases"],
                marker="o",
                markersize=3,
                linewidth=1.5,
                label=str(classification),
            )
        axis.set_title(f"{disease} statewide monthly cases — source categories kept separate")
        axis.set_ylabel("Reported cases")
        axis.grid(True, alpha=0.25)
        axis.legend(title="Source classification", fontsize=8)
    axes[-1].set_xlabel("Month")
    fig.suptitle("Descriptive surveillance trends (not a forecast)", fontsize=14)
    fig.tight_layout()
    fig.savefig(trend_path, dpi=160, bbox_inches="tight")
    plt.close(fig)

    weather = monthly_weather.copy()
    weather["period_start"] = pd.PeriodIndex(weather["period"], freq="M").to_timestamp()
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    axes[0].plot(weather["period_start"], weather["precipitation_sum_mm"], color="#176b87")
    axes[0].set_ylabel("Precipitation (mm)")
    axes[0].set_title("Monthly precipitation — equal-weight district-location proxy")
    axes[1].plot(weather["period_start"], weather["temperature_2m_mean_c"], color="#b2533e")
    axes[1].set_ylabel("Mean temperature (°C)")
    axes[1].set_title("Monthly mean temperature — equal-weight district-location proxy")
    for axis in axes:
        axis.grid(True, alpha=0.25)
    axes[-1].set_xlabel("Month")
    fig.tight_layout()
    fig.savefig(weather_path, dpi=160, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    for row, disease in enumerate(("Dengue", "Leptospirosis")):
        subset = data[data["disease"] == disease]
        for classification, group in subset.groupby("classification", sort=False):
            axes[row, 0].scatter(
                group["precipitation_sum_mm"], group["cases"], s=24, alpha=0.75,
                label=str(classification),
            )
            axes[row, 1].scatter(
                group["temperature_2m_mean_c"], group["cases"], s=24, alpha=0.75,
                label=str(classification),
            )
        axes[row, 0].set_ylabel(f"{disease} cases")
        axes[row, 0].set_xlabel("Monthly precipitation (mm)")
        axes[row, 1].set_xlabel("Monthly mean temperature (°C)")
        axes[row, 0].legend(title="Source classification", fontsize=7)
        axes[row, 1].legend(title="Source classification", fontsize=7)
        for axis in axes[row]:
            axis.grid(True, alpha=0.25)
    fig.suptitle("Exploratory monthly associations (descriptive; not causal)", fontsize=13)
    fig.tight_layout()
    fig.savefig(assoc_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return [path.relative_to(ROOT).as_posix() for path in (trend_path, weather_path, assoc_path)]


def _write_readiness(
    disease: pd.DataFrame,
    monthly_weather: pd.DataFrame,
    integrated: pd.DataFrame,
    unmatched_disease: list[str],
    unmatched_weather: list[str],
    associations: list[list[Any]],
    charts: list[str],
) -> None:
    category_summary = (
        disease.groupby(["year", "disease", "classification"], sort=True)
        .size()
        .rename("monthly_rows")
        .reset_index()
    )
    completeness = monthly_weather["weather_location_count"].eq(len(DISTRICT_LOCATIONS)).all()
    lines = [
        "# Analysis data readiness — statewide monthly disease and weather",
        "",
        f"- Generated (UTC): {_utc_now()}",
        f"- Disease source: `{DISEASE_CSV.relative_to(ROOT).as_posix()}` (read-only; no source rows changed).",
        f"- Integrated dataset: `{INTEGRATED_CSV.relative_to(ROOT).as_posix()}`",
        f"- Weather quality report: `{QUALITY_REPORT.relative_to(ROOT).as_posix()}`",
        "",
        "## Scope and source meaning",
        "",
        f"- Disease input has {len(disease)} statewide monthly rows across "
        f"{disease['period'].nunique()} observed months ({disease['period'].min()} to {disease['period'].max()}); "
        "it is not district-month disease data.",
        "- The annual district dataset is not used in this monthly join. No district-month disease values "
        "are inferred from annual counts.",
        "- Cases and deaths are retained from the statewide source; classifications remain distinct, "
        "including 2021 `reported_category_status_not_split`, 2022 "
        "`non_probable_category_probable_separate`, and 2023–2024 `Confirmed`.",
        "- The 2021 dengue difference documented in the existing audit (3,251 statewide monthly versus "
        "3,261 district confirmed annual total) remains unresolved and is not reconciled by this pipeline.",
        "- Empty disease months are not changed to zero. Missing reporting months stop this pipeline.",
        "",
        "### Disease coverage by source category",
        "",
        _markdown_table(
            ["Year", "Disease", "Source classification", "Rows"],
            category_summary.values.tolist(),
        ),
        "",
        "## Weather method",
        "",
        "- Source: Open-Meteo Historical Weather API, using daily `precipitation_sum` (mm) and "
        "`temperature_2m_mean/min/max` (°C) in `Asia/Kolkata`.",
        "- Fourteen representative locations, one approximate district-headquarters point per district, "
        "are documented in the acquisition script and raw response metadata.",
        "- Monthly precipitation is the equal-weight mean of the fourteen location-level monthly totals. "
        "Temperature metrics are equal-weight means of each location's monthly daily-temperature metric.",
        "- The resulting weather series is a **proxy**, not an official population-weighted statewide measure "
        "or a district-wide spatial average. API-selected historical model is not pinned.",
        "- Raw responses and request/retrieval metadata are preserved under "
        "`data/raw/open_meteo_weather/`; reruns reuse these files unless `--refresh` is specified.",
        "",
        "## Coverage and join validation",
        "",
        _markdown_table(
            ["Check", "Result"],
            [
                ["Disease/weather month overlap", f"{len(integrated['period'].unique())} joined months"],
                ["Unmatched disease months", ", ".join(unmatched_disease) or "None"],
                ["Unmatched weather months", ", ".join(unmatched_weather) or "None"],
                ["Monthly weather location completeness",
                 "PASS (14/14 locations)" if completeness else "FAIL"],
                ["Duplicate integrated natural keys",
                 str(int(integrated.duplicated(
                     ["period", "geography", "disease", "classification"]
                 ).sum()))],
                ["Integrated records", str(len(integrated))],
            ],
        ),
        "",
        "## Exploratory descriptive associations",
        "",
        "The table reports Pearson correlations of monthly cases with same-month weather **only as "
        "descriptive associations**. Correlation does not establish that weather causes disease changes. "
        "Reporting classifications are not harmonized across years, observations are few, and this analysis "
        "does not adjust for seasonality, reporting changes, population, lags, or confounders. No model was trained.",
        "",
        _markdown_table(
            ["Disease", "Source classification", "Weather measure", "Months (n)",
             "Pearson r", "Interpretation"],
            associations,
        ),
        "",
        "## Charts",
        "",
        *[f"- `{chart}`" for chart in charts],
        "",
        "## Readiness decision",
        "",
        "The joined dataset is suitable for a **limited descriptive, statewide exploratory analysis** "
        "for the observed periods and preserved reporting categories. It is not suitable for causal claims, "
        "district-level conclusions, robust lag inference, forecasting, or hospital-capacity prediction. "
        "The short 48-month statewide series and year-specific classification semantics are substantial limitations.",
        "",
        "## Recommended next step",
        "",
        "Obtain and validate a multi-year official monthly district-level disease extract with source definitions "
        "and reporting metadata before any district-level climate analysis or model work. Keep the current "
        "statewide output as a provenance-preserving exploratory baseline only.",
    ]
    READINESS_REPORT.parent.mkdir(parents=True, exist_ok=True)
    READINESS_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(refresh: bool = False) -> None:
    checks: list[tuple[str, str, str]] = []
    try:
        disease = _load_disease(checks)
        first_date = disease["period_start"].min().strftime("%Y-%m-01")
        last_date = (
            disease["period_start"].max() + pd.offsets.MonthEnd(0)
        ).strftime("%Y-%m-%d")
        daily = _acquire_weather(first_date, last_date, refresh, checks)
        monthly_weather = _monthly_weather(daily)
        disease_months = set(disease["period"].astype(str))
        weather_months = set(monthly_weather["period"].astype(str))
        unmatched_disease = sorted(disease_months - weather_months)
        unmatched_weather = sorted(weather_months - disease_months)
        if unmatched_disease or unmatched_weather:
            checks.append((
                "Disease/weather month alignment",
                "FAIL",
                f"Unmatched disease months={unmatched_disease}; unmatched weather months={unmatched_weather}.",
            ))
            raise PipelineError("Disease and weather do not cover the same observed months.")
        checks.append((
            "Disease/weather month alignment",
            "PASS",
            f"{len(disease_months)} exact YYYY-MM matches; no unmatched months.",
        ))

        monthly_dates = pd.PeriodIndex(monthly_weather["period"], freq="M")
        expected_days = monthly_dates.days_in_month
        if not monthly_weather["weather_location_count"].eq(len(DISTRICT_LOCATIONS)).all():
            raise PipelineError("One or more weather months lack one of the 14 representative locations.")
        if not np.array_equal(
            monthly_weather["weather_days_in_month"].to_numpy(dtype=int),
            np.asarray(expected_days, dtype=int),
        ):
            raise PipelineError("Monthly weather aggregation has missing daily observations.")
        if monthly_weather[list(WEATHER_COLUMNS.values())].isna().any().any():
            raise PipelineError("Monthly weather variables contain missing values; no imputation applied.")
        checks.append((
            "Monthly aggregation and missingness",
            "PASS",
            "All expected calendar days and 14 locations present per month; no values imputed.",
        ))

        integrated = disease.merge(
            monthly_weather,
            how="left",
            on="period",
            validate="many_to_one",
            indicator=True,
        )
        if not integrated["_merge"].eq("both").all():
            raise PipelineError("Some disease rows failed the many-to-one month join.")
        integrated = integrated.drop(columns=["_merge", "period_start"])
        if integrated.duplicated(["period", "geography", "disease", "classification"]).any():
            raise PipelineError("Duplicate integrated disease-weather natural keys detected.")
        checks.extend([
            ("Join keys and cardinality", "PASS",
             f"Many-to-one YYYY-MM join; {len(integrated)} records; no duplicate natural keys."),
            ("Measurement sanity after join", "PASS",
             "All weather measures are finite; precipitation ≥ 0; monthly temperatures remain in "
             "plausible API-validated range."),
        ])

        associations = _association_rows(integrated)
        charts = _write_charts(integrated, monthly_weather)
        weather_columns = [
            "precipitation_sum_mm",
            "temperature_2m_mean_c",
            "temperature_2m_min_c",
            "temperature_2m_max_c",
        ]
        if not np.isfinite(integrated[weather_columns].to_numpy(dtype=float)).all():
            raise PipelineError("Integrated weather columns contain non-finite values.")

        WEATHER_CSV.parent.mkdir(parents=True, exist_ok=True)
        monthly_weather.to_csv(WEATHER_CSV, index=False, encoding="utf-8")
        integrated.to_csv(INTEGRATED_CSV, index=False, encoding="utf-8")
        _write_quality_report(checks)
        _write_readiness(
            disease, monthly_weather, integrated, unmatched_disease, unmatched_weather,
            associations, charts,
        )
        print(f"SUCCESS: wrote weather monthly proxy ({len(monthly_weather)} rows): {WEATHER_CSV}")
        print(f"SUCCESS: wrote integrated disease-weather data ({len(integrated)} rows): {INTEGRATED_CSV}")
        print(f"SUCCESS: wrote quality report: {QUALITY_REPORT}")
        print(f"SUCCESS: wrote readiness report: {READINESS_REPORT}")
        print("Charts:")
        for chart in charts:
            print(f"  {ROOT / chart}")
    except PipelineError as exc:
        _write_quality_report(checks, str(exc))
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Fetch fresh API responses instead of reusing preserved raw response files.",
    )
    args = parser.parse_args()
    try:
        run(refresh=args.refresh)
    except (PipelineError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
