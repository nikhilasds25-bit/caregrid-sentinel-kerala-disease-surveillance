"""Versioned, read-only API endpoints for exploratory analytical results."""

from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from typing import Literal

from caregrid.data_access import ROOT

router = APIRouter(prefix="/api/v1", tags=["Exploratory Analytics"])


def load_dataset(relative_path: str) -> pd.DataFrame:
    """Load a prepared analytical dataset without running model training."""
    path = ROOT / relative_path

    try:
        return pd.read_csv(path)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Required analytical dataset is unavailable: {relative_path}",
        ) from exc


def respond(records: list[dict], filters: dict) -> dict:
    """Return the approved versioned response envelope."""
    return {
        "data": records,
        "meta": {
            "schema_version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "exploratory",
            "filters": filters,
            "limitations": [
                "Results are exploratory and not operational public-health alerts.",
                "Historical backtest predictions are not future forecasts.",
                "EWMA/CUSUM signals do not establish confirmed outbreaks.",
                "Q90 thresholds are statistical and not epidemiologically validated.",
                "Exceedance probabilities have not been validated as calibrated outbreak probabilities.",
                "No forecasting model is designated operationally ready."
            ],
        },
    }


def filter_data(frame: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply optional filters without changing source values."""
    selected = frame

    for column, value in filters.items():
        if value is not None and column in selected.columns:
            selected = selected.loc[selected[column] == value]

    return selected


@router.get("/forecasts")
def forecasts(
    disease: Literal["Dengue", "Leptospirosis"] | None = None,
    district: str | None = None,
    model_name: str | None = None,
    validation_phase: str | None = None,
):
    filters = {
        "disease": disease,
        "district": district,
        "model_name": model_name,
        "validation_phase": validation_phase,
    }

    frame = filter_data(
        load_dataset("outputs/chart_data/forecast_bands.csv"),
        filters,
    )

    frame = frame.drop(columns=["actual"], errors="ignore")

    records = frame.astype(object).where(pd.notna(frame), None).to_dict("records")

    for record in records:
        record["prediction_type"] = "backtest"

    return respond(records, filters)


@router.get("/model-comparisons")
def model_comparisons(
    disease: Literal["Dengue", "Leptospirosis"] | None = None,
    evidence_role: str | None = None,
    horizon_scope: str | None = None,
):
    filters = {
        "disease": disease,
        "evidence_role": evidence_role,
        "horizon_scope": horizon_scope,
    }

    frame = filter_data(
        load_dataset("outputs/chart_data/model_comparison.csv"),
        filters,
    )

    records = frame.astype(object).where(pd.notna(frame), None).to_dict("records")

    return respond(records, filters)


@router.get("/detection/signals")
def detection_signals(
    disease: Literal["Dengue", "Leptospirosis"] | None = None,
    district: str | None = None,
    detector_id: str | None = None,
):
    filters = {
        "disease": disease,
        "district": district,
        "detector_id": detector_id,
    }

    frame = filter_data(
        load_dataset("outputs/anomaly_chart_data/anomaly_signals.csv"),
        filters,
    )

    records = frame.astype(object).where(pd.notna(frame), None).to_dict("records")

    return respond(records, filters)


@router.get("/exceedance/assessments")
def exceedance_assessments(
    disease: Literal["Dengue", "Leptospirosis"] | None = None,
    district: str | None = None,
    model_name: str | None = None,
):
    filters = {
        "disease": disease,
        "district": district,
        "model_name": model_name,
    }

    frame = filter_data(
        load_dataset("outputs/exceedance_chart_data/exceedance_chart_data.csv"),
        filters,
    )

    frame = frame.drop(columns=["actual"], errors="ignore")

    records = frame.astype(object).where(pd.notna(frame), None).to_dict("records")

    return respond(records, filters)


@router.get("/surveillance/observations")
def surveillance_observations(
    source: Literal["curated", "district_dashboard"] = "curated",
    disease: Literal["Dengue", "Leptospirosis"] | None = None,
    district: str | None = None,
    classification: str | None = None,
    granularity: str = Query(default="monthly", pattern="^(monthly|annual)$"),
    year: int | None = Query(default=None, ge=2020, le=2024),
):
    """Return source-native observations, not model-generated predictions."""
    from caregrid.data_access import DataRepository, DatasetUnavailable

    if source == "district_dashboard":
        if granularity != "monthly":
            raise HTTPException(
                status_code=422,
                detail="District dashboard observations are monthly only.",
            )

        from caregrid.outbreak_detection import load_confirmed_observations

        relative_path = (
            "data/candidates/"
            "kerala_district_monthly_disease_dashboard_2016_2025.csv"
        )

        try:
            frame = load_confirmed_observations(ROOT / relative_path)
        except (OSError, ValueError, KeyError, pd.errors.ParserError) as exc:
            raise HTTPException(
                status_code=503,
                detail="District-month observations are unavailable.",
            ) from exc

        filters = {
            "source": source,
            "disease": disease,
            "district": district,
            "classification": classification,
            "granularity": granularity,
            "year": year,
        }

        if disease is not None:
            frame = frame.loc[frame["disease"] == disease]
        if district is not None:
            frame = frame.loc[frame["district"] == district]
        if year is not None:
            frame = frame.loc[frame["period"].str[:4] == str(year)]
        if classification is not None and classification != "Confirmed":
            frame = frame.iloc[0:0]

        records = [
            {
                "disease": row.disease,
                "district": row.district,
                "reporting_period": row.period,
                "observed_count": int(row.cases),
                "classification": "Confirmed",
                "temporal_granularity": "monthly",
                "observation_type": "reported_observation",
            }
            for row in frame.itertuples(index=False)
        ]

        response = respond(records, filters)
        response["meta"]["geographic_granularity"] = "district"
        response["meta"]["source_dataset"] = relative_path
        response["meta"]["source_scope"] = (
            "Kerala Health Department dashboard; available Confirmed counts only"
        )
        return response

    try:
        data = DataRepository.load()
    except DatasetUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    filters = {
        "disease": disease,
        "district": district,
        "classification": classification,
        "granularity": granularity,
        "year": year,
    }

    frame = data.monthly.copy() if granularity == "monthly" else data.annual.copy()

    if district is not None:
        if granularity == "monthly":
            raise HTTPException(
                status_code=422,
                detail="District-level monthly observations are unavailable.",
            )
        frame = frame.loc[frame["district"] == district]

    for column, value in {
        "disease": disease,
        "classification": classification,
        "year": year,
    }.items():
        if value is not None:
            frame = frame.loc[frame[column] == value]

    records = frame.astype(object).where(pd.notna(frame), None).to_dict("records")

    for record in records:
        record["observed_count"] = record.pop("cases")
        record["reporting_period"] = (
            record["period"] if granularity == "monthly" else str(record["year"])
        )
        record["temporal_granularity"] = granularity
        record["observation_type"] = "reported_observation"

    response = respond(records, filters)
    response["meta"]["geographic_granularity"] = (
        "statewide" if granularity == "monthly" else "district"
    )

    return response
