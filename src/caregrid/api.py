"""FastAPI endpoints for the validated, read-only CareGrid datasets."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from caregrid.data_access import DataRepository, DatasetUnavailable, ROOT
from caregrid.daily_surveillance import (
    DAILY_DIR,
    DailySurveillanceUnavailable,
    cumulative_statistics,
    daily_time_series,
    daily_statistics,
    district_daily_statistics,
    get_daily_source_status,
    get_latest_daily_report,
    load_daily_snapshot,
    load_backfill_status,
    period_summary,
)
from caregrid.surveillance import (
    SOURCE_INDEX_URL,
    SOURCE_NAME,
    SOURCE_PDF_URL,
    SurveillanceUnavailable,
    dataset_info,
    district_statistics,
    get_source_status,
    latest_summary,
    load_snapshot,
    trend_records,
)
from caregrid.forecasting import ForecastExperimentError, load_experiment_artifact


app = FastAPI(
    title="CareGrid Sentinel Data API",
    version="1.0.0",
    description=(
        "Read-only access to curated Kerala disease and historical weather datasets. "
        "This API does not provide forecasts, alerts, clinical advice, or real hospital capacity."
    ),
)


def repository() -> DataRepository:
    try:
        return DataRepository.load()
    except DatasetUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/forecasting/experiment")
def forecasting_experiment() -> dict:
    try:
        return load_experiment_artifact()
    except ForecastExperimentError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/health")
def health() -> dict:
    try:
        return DataRepository.load().status()
    except DatasetUnavailable as exc:
        return {
            "status": "degraded",
            "datasets": {},
            "error": str(exc),
        }


@app.get("/api/live-surveillance/daily/trends")
def daily_idsp_trends(
        disease: Literal["Dengue", "Leptospirosis"] = Query(default="Dengue"),
) -> dict:
        try:
            series = daily_time_series(disease)
            end_date = pd.Timestamp(series["reporting_period_end"]).date()
            return {
                **series,
                "summaries": {
                    "7_day": period_summary(disease, end_date=end_date, days=7),
                    "30_day": period_summary(disease, end_date=end_date, days=30),
                },
                "previous_period_comparisons_require_complete_source_values": True,
                "cumulative_values_used_in_trend_calculation": False,
            }
        except DailySurveillanceUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/overview")
def overview() -> dict:
    data = repository()
    monthly = data.monthly
    annual = data.annual
    totals = (
        monthly.groupby(["year", "disease", "classification"], as_index=False, sort=True)
        .agg(cases=("cases", "sum"), deaths=("deaths", "sum"))
        .to_dict(orient="records")
    )
    latest = monthly.loc[monthly["period"] == monthly["period"].max()]
    years = sorted(pd.to_numeric(annual["year"], errors="raise").astype(int).unique().tolist())
    return {
        "coverage": {
            "monthly_period_start": str(monthly["period"].min()),
            "monthly_period_end": str(monthly["period"].max()),
            "monthly_periods": int(monthly["period"].nunique()),
            "monthly_records": int(len(monthly)),
            "annual_year_start": int(min(years)),
            "annual_year_end": int(max(years)),
            "annual_district_records": int(len(annual)),
            "districts": int(annual["district"].nunique()),
            "diseases": sorted(monthly["disease"].astype(str).unique().tolist()),
            "latest_month": str(monthly["period"].max()),
            "latest_month_records": int(len(latest)),
        },
        "annual_statewide_totals": totals,
        "classification_by_year": _classification_by_year(monthly),
        "forecasting_available": False,
    }


@app.get("/api/disease/monthly")
def monthly_disease(
    disease: Literal["Dengue", "Leptospirosis"] | None = None,
    year: int | None = Query(default=None, ge=2021, le=2024),
    classification: str | None = None,
) -> dict:
    data = repository().monthly
    selected = data.copy()
    if disease:
        selected = selected.loc[selected["disease"] == disease]
    if year is not None:
        selected = selected.loc[selected["year"] == year]
    if classification:
        if classification not in set(data["classification"].astype(str)):
            choices = sorted(data["classification"].astype(str).unique().tolist())
            raise HTTPException(
                status_code=422,
                detail=f"Unknown source classification. Available source labels: {choices}",
            )
        selected = selected.loc[selected["classification"] == classification]
    return {
        "filters": {
            "disease": disease,
            "year": year,
            "classification": classification,
        },
        "options": {
            "diseases": sorted(data["disease"].astype(str).unique().tolist()),
            "years": sorted(pd.to_numeric(data["year"], errors="raise").astype(int).unique().tolist()),
            "classifications": sorted(data["classification"].astype(str).unique().tolist()),
        },
        "records": _records(selected),
    }


@app.get("/api/districts")
def district_comparison(
    year: int = Query(default=2024, ge=2020, le=2024),
    disease: Literal["Dengue", "Leptospirosis"] = "Dengue",
    classification: Literal["Confirmed", "Probable"] = "Confirmed",
) -> dict:
    selected = repository().annual
    selected = selected.loc[
        (selected["year"] == year)
        & (selected["disease"] == disease)
        & (selected["classification"] == classification)
    ].sort_values(["cases", "district"], ascending=[False, True])
    return {
        "year": year,
        "disease": disease,
        "classification": classification,
        "temporal_granularity": "annual",
        "records": _records(selected),
    }


@app.get("/api/climate")
def climate_insights(
    disease: Literal["Dengue", "Leptospirosis"] = "Dengue",
    classification: str | None = None,
) -> dict:
    data = repository()
    monthly = data.integrated
    selected = monthly.loc[monthly["disease"] == disease]
    if classification:
        if classification not in set(monthly["classification"].astype(str)):
            raise HTTPException(status_code=422, detail="Unknown source classification.")
        selected = selected.loc[selected["classification"] == classification]
    rows = _records(selected)
    weather = _records(data.weather)
    if not set(row["period"] for row in rows).issubset(
        set(row["period"] for row in weather)
    ):
        raise HTTPException(status_code=503, detail="Weather coverage does not match disease months.")
    return {
        "disease": disease,
        "classification": classification,
        "weather_scope": "Equal-weight mean of 14 representative district locations; statewide proxy",
        "weather": weather,
        "disease_records": rows,
        "classification_options": sorted(monthly["classification"].astype(str).unique().tolist()),
    }


@app.get("/api/methodology")
def methodology() -> dict:
    data = repository()
    monthly = data.monthly
    annual = data.annual
    classifications = _classification_by_year(monthly)
    try:
        daily_snapshot = load_daily_snapshot()
        daily_status = get_daily_source_status()
    except DailySurveillanceUnavailable:
        daily_snapshot = None
        daily_status = {
            "status": "data_not_available",
            "snapshot_available": False,
            "report_date": None,
            "last_successful_retrieval": None,
            "source_index_url": "https://dhs.kerala.gov.in/en/idsp-2/",
            "source_url": None,
        }
    return {
        "sources": [
            {
                "name": "Kerala DHS IDSP daily surveillance reports",
                "coverage": (
                    daily_snapshot["report_date"] if daily_snapshot else "No validated daily report imported"
                ),
                "records": (
                    len(daily_snapshot["statewide_records"]) if daily_snapshot else 0
                ),
                "urls": [
                    daily_status["source_index_url"],
                    *([daily_status["source_url"]] if daily_status.get("source_url") else []),
                ],
                "grain": (
                    "Statewide daily, present-month and cumulative 2026 values; "
                    "district daily values where present and validated"
                ),
                "status": daily_status["status"],
                "report_date": daily_status.get("report_date"),
                "source_published_at": daily_status.get("source_post_published_at"),
                "last_retrieval": daily_status.get("last_successful_retrieval"),
                "reporting_frequency": "Daily report index; report date shown per snapshot",
                "limitations": [
                    "Source labels the report preliminary; cumulative totals are running values.",
                    "Daily snapshot is separate from historical monthly and 2025 annual records.",
                ],
            },
            {
                "name": "Kerala DHS monthly communicable-disease reports",
                "coverage": f"{monthly['period'].min()} to {monthly['period'].max()}",
                "records": int(len(monthly)),
                "urls": sorted(monthly["source_url"].astype(str).unique().tolist()),
                "grain": "Statewide monthly; cases and deaths",
            },
            {
                "name": "Kerala Health Department districtwise cases/deaths workbooks",
                "coverage": "2020–2024",
                "records": int(len(annual)),
                "urls": sorted(
                    set(annual["case_source_url"].astype(str))
                    | set(annual["death_source_url"].astype(str))
                ),
                "grain": "Annual district records; confirmed/probable preserved separately",
            },
            {
                "name": "Open-Meteo Historical Weather API",
                "coverage": f"{data.weather['period'].min()} to {data.weather['period'].max()}",
                "records": int(len(data.weather)),
                "urls": ["https://archive-api.open-meteo.com/v1/archive"],
                "documentation": "https://open-meteo.com/en/docs/historical-weather-api",
                "grain": "Daily source data aggregated to monthly precipitation (mm) and temperatures (°C)",
            },
        ],
        "classification_by_year": classifications,
        "caveats": [
            "The 2021 statewide monthly dengue total is 3,251; the district annual confirmed sum is 3,261 (difference +10). The discrepancy remains unresolved.",
            "The monthly disease dataset is statewide; annual district totals must not be interpreted as district-month observations.",
            "2021 reported_category_status_not_split, 2022 non_probable_category_probable_separate, and 2023–2024 Confirmed categories are not harmonized.",
            "Weather is an equal-weight proxy from 14 approximate district-headquarters locations, not a population-weighted statewide measurement.",
            "Weather/disease association is descriptive and cannot establish causation.",
            "A limited 2023-to-2024 baseline hindcast is available for explicitly Confirmed monthly records. It is experimental and does not provide operational future forecasts or risk scores; see the forecasting experiment report.",
            "The application is not a medical diagnostic tool.",
            "The 2026 daily DHS IDSP report is provisional and separate from the 2025 annual and 2021–2024 historical datasets.",
            "No verified official hospital capacity feed is connected; the capacity simulator is hypothetical only.",
        ],
        "reports": [
            "reports/analysis_data_readiness.md",
            "reports/weather_data_quality_report.md",
            "reports/data_quality_audit_latest.md",
            "reports/district_monthly_data_source.md",
            "reports/live_kerala_surveillance_data_quality.md",
            "reports/daily_idsp_data_quality_report.md",
        ],
        "forecasting_available": False,
        "forecasting_experiment_available": True,
        "district_boundary_data_available": False,
    }


def _surveillance_snapshot() -> dict:
    try:
        return load_snapshot()
    except SurveillanceUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "No valid official DHS surveillance snapshot is currently available. "
                f"The historical dataset endpoints remain separate. {exc}"
            ),
        ) from exc


@app.get("/api/live-surveillance/summary")
def live_surveillance_summary() -> dict:
    return latest_summary()


@app.get("/api/live-surveillance/diseases")
def live_disease_statistics(
    disease: str | None = Query(default=None, min_length=1, max_length=100),
    classification: str | None = Query(default=None, min_length=1, max_length=100),
) -> dict:
    summary = latest_summary()
    records = summary["disease_statistics"]
    disease_options = sorted({row["disease"] for row in records})
    classification_options = sorted({row["classification"] for row in records})
    if disease and disease.casefold() not in {value.casefold() for value in disease_options}:
        raise HTTPException(status_code=422, detail="Disease is not present in the official snapshot.")
    if classification and classification.casefold() not in {
        value.casefold() for value in classification_options
    }:
        raise HTTPException(status_code=422, detail="Classification is not present in the official snapshot.")
    filtered = [
        row for row in records
        if (disease is None or row["disease"].casefold() == disease.casefold())
        and (
            classification is None
            or row["classification"].casefold() == classification.casefold()
        )
    ]
    return {
        "data_status": summary["data_status"],
        "reporting_period_start": summary["reporting_period_start"],
        "reporting_period_end": summary["reporting_period_end"],
        "disease": disease,
        "classification": classification,
        "disease_options": disease_options,
        "classification_options": classification_options,
        "records": filtered,
    }


@app.get("/api/live-surveillance/districts")
def live_district_statistics(
    disease: str | None = Query(default=None, min_length=1, max_length=100),
    classification: str | None = Query(default=None, min_length=1, max_length=100),
) -> dict:
    snapshot = _surveillance_snapshot()
    disease_options = sorted({row["disease"] for row in snapshot["district_annual_records"]})
    classification_options_by_disease = {
        disease_name: sorted({
            row["classification"] for row in snapshot["district_annual_records"]
            if row["disease"] == disease_name
        })
        for disease_name in disease_options
    }
    classification_options = sorted({
        classification
        for options in classification_options_by_disease.values()
        for classification in options
    })
    if disease and disease.casefold() not in {value.casefold() for value in disease_options}:
        raise HTTPException(status_code=422, detail="Disease has no official district records.")
    if classification and classification.casefold() not in {
        value.casefold() for value in classification_options
    }:
        raise HTTPException(status_code=422, detail="Classification has no official district records.")
    result = district_statistics(disease, classification)
    return {
        "data_status": get_source_status()["status"],
        "reporting_year": result["reporting_year"],
        "reporting_frequency": result["reporting_frequency"],
        "temporal_granularity": result["temporal_granularity"],
        "disease": disease,
        "classification": classification,
        "disease_options": disease_options,
        "classification_options": classification_options,
        "classification_options_by_disease": classification_options_by_disease,
        "records": result["records"],
        "reported_districts": result["reported_districts"],
        "missing_districts": result["missing_districts"],
        "expected_district_count": result["expected_district_count"],
        "comparison_note": result["comparison_note"],
        "source_url": result["source_url"],
    }


@app.get("/api/live-surveillance/trends")
def live_surveillance_trends(
    disease: str | None = Query(default=None, min_length=1, max_length=100),
    classification: str | None = Query(default=None, min_length=1, max_length=100),
) -> dict:
    snapshot = _surveillance_snapshot()
    disease_options = sorted({row["disease"] for row in snapshot["monthly_records"]})
    classification_options_by_disease = {
        disease_name: sorted({
            row["classification"] for row in snapshot["monthly_records"]
            if row["disease"] == disease_name
        })
        for disease_name in disease_options
    }
    classification_options = sorted({
        classification
        for options in classification_options_by_disease.values()
        for classification in options
    })
    if disease and disease.casefold() not in {value.casefold() for value in disease_options}:
        raise HTTPException(status_code=422, detail="Disease is not present in the official monthly report.")
    if classification and classification.casefold() not in {
        value.casefold() for value in classification_options
    }:
        raise HTTPException(status_code=422, detail="Classification is not present in the official monthly report.")
    return {
        "data_status": get_source_status()["status"],
        "frequency": "monthly",
        "reporting_period_start": snapshot["reporting_period_start"],
        "reporting_period_end": snapshot["reporting_period_end"],
        "disease": disease,
        "classification": classification,
        "disease_options": disease_options,
        "classification_options": classification_options,
        "classification_options_by_disease": classification_options_by_disease,
        "records": trend_records(disease, classification),
        "source_url": snapshot["source_url"],
    }


@app.get("/api/live-surveillance/source-status")
def live_surveillance_source_status() -> dict:
    return get_source_status()


@app.get("/api/live-surveillance/last-update")
def live_surveillance_last_update() -> dict:
    status = get_source_status()
    return {
        "last_successful_retrieval": status.get("last_successful_retrieval"),
        "last_attempt": status.get("last_attempt"),
        "dataset_version": status.get("dataset_version"),
        "reporting_period": status.get("reporting_period"),
        "source_status": status["status"],
    }


@app.get("/api/live-surveillance/source")
def live_surveillance_source() -> dict:
    status = get_source_status()
    if not status["snapshot_available"]:
        return {
            "source_name": SOURCE_NAME,
            "source_index_url": SOURCE_INDEX_URL,
            "source_url": SOURCE_PDF_URL,
            "source_status": status,
            "retrieval_method": (
                "Manually verified official DHS PDF; automated access is restricted to the exact "
                "verified PDF URL. No public API was identified."
            ),
            "publication_date": None,
            "last_retrieval_timestamp": None,
            "reporting_frequency": "Annual report with monthly tables when published",
            "available_variables": [],
            "validation_status": "no verified snapshot available",
            "limitations": ["Current official data unavailable; no verified snapshot is loaded."],
        }
    return dataset_info()


def _daily_snapshot() -> dict:
    try:
        return load_daily_snapshot()
    except DailySurveillanceUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "No valid daily DHS IDSP snapshot is currently available. "
                f"The separate annual and historical datasets remain unchanged. {exc}"
            ),
        ) from exc


def _daily_source_status() -> dict:
    try:
        return get_daily_source_status()
    except DailySurveillanceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/live-surveillance/daily/latest")
def daily_idsp_latest() -> dict:
    try:
        return get_latest_daily_report()
    except DailySurveillanceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/live-surveillance/daily/cumulative")
def daily_idsp_cumulative() -> dict:
    try:
        snapshot = _daily_snapshot()
        return {
            "report_date": snapshot["report_date"],
            "metric_period": "Cumulative 2026",
            "note": "Cumulative figures are running totals as reported, not daily observations.",
            "records": cumulative_statistics(),
            "source_url": snapshot["source_url"],
        }
    except DailySurveillanceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/live-surveillance/daily/diseases/daily")
def daily_idsp_disease_counts() -> dict:
    try:
        snapshot = _daily_snapshot()
        return {
            "report_date": snapshot["report_date"],
            "metric_period": "Daily",
            "records": daily_statistics("daily"),
            "source_url": snapshot["source_url"],
        }
    except DailySurveillanceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/live-surveillance/daily/diseases/month-to-date")
def daily_idsp_month_to_date_counts() -> dict:
    try:
        snapshot = _daily_snapshot()
        return {
            "report_date": snapshot["report_date"],
            "metric_period": "Present Month",
            "records": daily_statistics("present_month"),
            "source_url": snapshot["source_url"],
        }
    except DailySurveillanceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/live-surveillance/daily/districts")
def daily_idsp_district_counts(
    disease: str | None = Query(default=None, min_length=1, max_length=100),
    disease_subtype: str | None = Query(default=None, min_length=1, max_length=100),
) -> dict:
    try:
        snapshot = _daily_snapshot()
        supported_diseases = {
            row["disease"] for row in snapshot["district_records"]
        }
        if snapshot["daily_district_report_available"] and disease and disease.casefold() not in {
            value.casefold() for value in supported_diseases
        }:
            raise HTTPException(
                status_code=422,
                detail="Disease is not present in the official daily district report.",
            )
        result = district_daily_statistics(disease, disease_subtype)
        result["disease_options"] = sorted(supported_diseases)
        return result
    except DailySurveillanceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/live-surveillance/daily/latest-date")
def daily_idsp_latest_date() -> dict:
    status = _daily_source_status()
    return {
        "report_date": status.get("report_date"),
        "last_successful_retrieval": status.get("last_successful_retrieval"),
        "source_status": status["status"],
        "snapshot_available": status["snapshot_available"],
    }


@app.get("/api/live-surveillance/daily/source-status")
def daily_idsp_source_status() -> dict:
    return _daily_source_status()


@app.get("/api/live-surveillance/daily/last-update")
def daily_idsp_last_update() -> dict:
    status = _daily_source_status()
    return {
        "report_date": status.get("report_date"),
        "last_successful_retrieval": status.get("last_successful_retrieval"),
        "last_attempt": status.get("last_attempt"),
        "dataset_version": status.get("dataset_version"),
        "source_status": status["status"],
    }


@app.get("/api/live-surveillance/daily/source")
def daily_idsp_source() -> dict:
    status = _daily_source_status()
    if not status["snapshot_available"]:
        return {
            "source_name": status["source_name"],
            "source_index_url": status["source_index_url"],
            "source_status": status,
            "retrieval_method": (
                "Dated report post discovered from the official DHS IDSP index; PDF attachment "
                "URL is extracted from that post. No public API was identified."
            ),
            "reporting_frequency": "Daily report index, with actual report date shown per snapshot",
            "report_date": None,
            "source_post_published_at": None,
            "last_retrieval_timestamp": None,
            "available_variables": [],
            "validation_status": "no verified daily snapshot available",
            "hospital_capacity_data_connected": False,
            "hospital_capacity_note": (
                "No verified official hospital bed occupancy, ICU occupancy, available-bed, oxygen-capacity, "
                "or hospital-wise patient-load feed is connected. The simulator remains hypothetical only."
            ),
            "limitations": [
                "Current daily official data unavailable; no historical dataset is substituted.",
                "No verified official bed-occupancy, ICU, oxygen-capacity, or hospital-load feed is connected.",
            ],
            "count_dash_policy": (
                "The source provides no legend defining a printed hyphen; it remains uninterpreted and is not zero."
            ),
        }
    snapshot = _daily_snapshot()
    return {
        "source_name": snapshot["source_name"],
        "source_index_url": snapshot["source_index_url"],
        "source_page_url": snapshot["source_page_url"],
        "source_url": snapshot["source_url"],
        "source_status": status,
        "retrieval_method": (
            "The importer discovers dated posts from the official DHS IDSP index, extracts the "
            "PDF link from each post, and preserves the downloaded PDF before parsing."
        ),
        "reporting_frequency": "Daily IDSP report",
        "report_date": snapshot["report_date"],
        "source_post_published_at": snapshot.get("source_post_published_at"),
        "last_retrieval_timestamp": snapshot["retrieved_at_utc"],
        "available_variables": [
            "Statewide disease/subtype labels",
            "Suspected and confirmed cases and deaths",
            "Daily, present-month and cumulative-2026 totals",
            "District-coded daily counts where the district table is present",
        ],
        "validation_status": snapshot["validation_status"],
        "validation_checks": snapshot["validation_checks"],
        "dataset_version": snapshot["dataset_version"],
        "source_sha256": snapshot["source_sha256"],
        "parser_version": snapshot["parser_version"],
        "district_reconciliation": snapshot["district_reconciliation"],
        "count_dash_policy": snapshot["count_dash_policy"],
        "backfill_status": load_backfill_status(),
        "quality_flags": snapshot["quality_flags"],
        "district_report_error": snapshot["district_report_error"],
        "hospital_capacity_data_connected": False,
        "hospital_capacity_note": (
            "No verified official hospital bed occupancy, ICU occupancy, available-bed, oxygen "
            "capacity, or hospital-wise patient-load source was identified in the DHS pages "
            "inspected. The separate simulator remains hypothetical only."
        ),
        "limitations": [
            "The report labels its counts preliminary and subject to change after laboratory tests and death audits.",
            "The PDF provides no legend defining a printed hyphen in count cells. Hyphens are retained as uninterpreted source dashes, not converted to zero.",
            "Daily district table has one reported-deaths field; it is not assigned to suspected or confirmed cases.",
            "Cumulative 2026 values are running totals and are not added across report dates.",
            "Daily disease reports are separate from the 2025 annual report and 2021–2024 historical datasets.",
            "No real hospital capacity feed is connected.",
        ],
        "raw_pdf": snapshot.get("original_file"),
    }


@app.get("/api/reports/{report_name}")
def read_report(report_name: str) -> FileResponse:
    allowed = {
        "analysis_data_readiness.md",
        "weather_data_quality_report.md",
        "data_quality_audit_latest.md",
        "district_monthly_data_source.md",
        "live_kerala_surveillance_data_quality.md",
        "daily_idsp_data_quality_report.md",
        "forecasting_readiness_audit.md",
        "forecasting_experiment_report.md",
        "forecasting_readiness_audit.md",
        "forecasting_experiment_report.md",
    }
    if report_name not in allowed:
        raise HTTPException(status_code=404, detail="Report not found.")
    report_path = ROOT / "reports" / report_name
    if not report_path.is_file():
        raise HTTPException(status_code=404, detail=f"Project report is missing: reports/{report_name}")
    return FileResponse(report_path, media_type="text/markdown; charset=utf-8")


def _classification_by_year(monthly: pd.DataFrame) -> list[dict]:
    grouped = (
        monthly.groupby(["year", "classification"], sort=True)
        .size()
        .rename("records")
        .reset_index()
    )
    return _records(grouped)


def _records(frame: pd.DataFrame) -> list[dict]:
    clean = frame.copy()
    clean = clean.astype(object).where(pd.notna(clean), None)
    return clean.to_dict(orient="records")


frontend_dist = ROOT / "dashboard" / "dist"
if frontend_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path.startswith("api/") or path.startswith("docs") or path.startswith("openapi"):
            raise HTTPException(status_code=404, detail="Not found")
        target = (frontend_dist / path).resolve()
        if not target.is_relative_to(frontend_dist.resolve()) or not target.is_file():
            target = frontend_dist / "index.html"
        return FileResponse(target)
