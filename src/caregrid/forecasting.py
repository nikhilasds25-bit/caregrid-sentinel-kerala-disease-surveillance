"""Reproducible, baseline-only forecasting experiment for compatible monthly series."""
from __future__ import annotations

import json
import hashlib
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from caregrid.data_access import DataRepository, ROOT


EXPERIMENT_DIR = Path("reports/forecasting_experiment")
FIGURE_DIR = Path("reports/figures")
READINESS_REPORT = Path("reports/forecasting_readiness_audit.md")
EXPERIMENT_REPORT = Path("reports/forecasting_experiment_report.md")
HOLDOUT_START = "2024-01"
HOLDOUT_END = "2024-12"
TRAIN_START = "2023-01"
TRAIN_END = "2023-12"
SEASONALITY = 12
PRIMARY_DISEASES = ("Dengue", "Leptospirosis")
BASELINE_NAMES = ("naive", "seasonal_naive")


class ForecastExperimentError(ValueError):
    """Input data cannot support a requested forecasting operation."""


def _finite_series(values: Sequence[float], name: str) -> list[float]:
    result = []
    for value in values:
        if value is None or pd.isna(value):
            raise ForecastExperimentError(f"{name} cannot contain missing values.")
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ForecastExperimentError(f"{name} must contain finite values.")
        result.append(numeric)
    return result


def naive_forecast(training_values: Sequence[float], horizon: int) -> list[float]:
    """Repeat the last observed training value for each requested step."""
    training = _finite_series(training_values, "Training values")
    if not training:
        raise ForecastExperimentError("Naive forecasting requires at least one observation.")
    if horizon < 1:
        raise ForecastExperimentError("Forecast horizon must be at least one.")
    return [training[-1]] * horizon


def seasonal_naive_forecast(
    training_values: Sequence[float],
    horizon: int,
    seasonality: int = SEASONALITY,
) -> list[float]:
    """Repeat the latest observed seasonal cycle without fitting on future data."""
    training = _finite_series(training_values, "Training values")
    if seasonality < 1:
        raise ForecastExperimentError("Seasonality must be at least one.")
    if len(training) < seasonality:
        raise ForecastExperimentError(
            f"Seasonal-naive forecasting needs at least {seasonality} training observations."
        )
    if horizon < 1:
        raise ForecastExperimentError("Forecast horizon must be at least one.")
    cycle = training[-seasonality:]
    return [cycle[index % seasonality] for index in range(horizon)]


def chronological_split(
    frame: pd.DataFrame,
    *,
    period_column: str = "period",
    train_end: str,
    test_start: str,
    test_end: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a monthly frame on an explicit chronological boundary."""
    if period_column not in frame.columns:
        raise ForecastExperimentError(f"Missing period column {period_column!r}.")
    data = frame.copy()
    periods = pd.PeriodIndex(data[period_column].astype(str), freq="M")
    if periods.has_duplicates:
        raise ForecastExperimentError("Chronological split rejected duplicate monthly periods.")
    if not periods.is_monotonic_increasing:
        raise ForecastExperimentError("Chronological split requires periods in ascending order.")
    train_limit = pd.Period(train_end, freq="M")
    test_first = pd.Period(test_start, freq="M")
    test_last = pd.Period(test_end, freq="M")
    if train_limit >= test_first or test_first > test_last:
        raise ForecastExperimentError("Training and test period boundaries overlap or are invalid.")
    train_mask = periods <= train_limit
    test_mask = (periods >= test_first) & (periods <= test_last)
    train, test = data.loc[train_mask].copy(), data.loc[test_mask].copy()
    if train.empty or test.empty:
        raise ForecastExperimentError("Chronological split produced an empty training or test set.")
    if max(pd.Period(value, freq="M") for value in train[period_column]) >= min(
        pd.Period(value, freq="M") for value in test[period_column]
    ):
        raise ForecastExperimentError("Chronological split would leak test observations into training.")
    return train.reset_index(drop=True), test.reset_index(drop=True)


def calculate_metrics(
    actual: Sequence[float],
    predicted: Sequence[float],
    training_values: Sequence[float],
    *,
    seasonality: int = SEASONALITY,
) -> dict[str, float | None]:
    """Calculate MAE, RMSE, and seasonal MASE using training-only scaling."""
    observed = _finite_series(actual, "Actual values")
    estimates = _finite_series(predicted, "Predictions")
    training = _finite_series(training_values, "Training values")
    if not observed or len(observed) != len(estimates):
        raise ForecastExperimentError("Actual and predicted values must have equal, nonzero lengths.")
    if seasonality < 1:
        raise ForecastExperimentError("Seasonality must be at least one.")
    errors = np.asarray(observed, dtype=float) - np.asarray(estimates, dtype=float)
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(np.square(errors))))
    mase: float | None = None
    if len(training) > seasonality:
        scale = float(np.mean(np.abs(
            np.asarray(training[seasonality:], dtype=float)
            - np.asarray(training[:-seasonality], dtype=float)
        )))
        if scale > 0 and math.isfinite(scale):
            mase = mae / scale
    return {"mae": mae, "rmse": rmse, "mase": mase}


def align_climate_features(
    disease_frame: pd.DataFrame,
    weather_frame: pd.DataFrame,
    *,
    period_column: str = "period",
) -> pd.DataFrame:
    """One-to-one month alignment for an audit; returned weather is not future-known."""
    if period_column not in disease_frame or period_column not in weather_frame:
        raise ForecastExperimentError("Disease and weather data must both contain monthly period keys.")
    if disease_frame[period_column].duplicated().any() or weather_frame[period_column].duplicated().any():
        raise ForecastExperimentError("Climate alignment rejects duplicate monthly keys.")
    weather_columns = [
        period_column,
        "precipitation_sum_mm",
        "temperature_2m_mean_c",
        "temperature_2m_min_c",
        "temperature_2m_max_c",
    ]
    missing_columns = sorted(set(weather_columns) - set(weather_frame.columns))
    if missing_columns:
        raise ForecastExperimentError(
            "Weather data is missing columns: " + ", ".join(missing_columns)
        )
    merged = disease_frame.merge(
        weather_frame[weather_columns],
        on=period_column,
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    if not merged["_merge"].eq("both").all():
        missing = merged.loc[merged["_merge"] != "both", period_column].astype(str).tolist()
        raise ForecastExperimentError(
            "Weather does not cover every disease month: " + ", ".join(missing)
        )
    return merged.drop(columns="_merge")


def series_readiness(group: pd.DataFrame) -> dict[str, Any]:
    ordered = group.sort_values("period")
    periods = ordered["period"].astype(str).tolist()
    start, end = pd.Period(periods[0], freq="M"), pd.Period(periods[-1], freq="M")
    expected = pd.period_range(start, end, freq="M").astype(str).tolist()
    present = set(periods)
    values = pd.to_numeric(ordered["cases"], errors="coerce")
    q1, q3 = values.quantile(0.25), values.quantile(0.75)
    iqr = q3 - q1
    outliers = []
    if iqr > 0:
        mask = (values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)
        outliers = [
            {"period": str(row.period), "cases": int(row.cases)}
            for row in ordered.loc[mask, ["period", "cases"]].itertuples(index=False)
        ]
    source_files = sorted(ordered["source_file"].astype(str).unique().tolist())
    notes = sorted(ordered["classification_note"].astype(str).unique().tolist())
    return {
        "valid_observations": int(values.notna().sum()),
        "first_reporting_month": periods[0],
        "last_reporting_month": periods[-1],
        "missing_months": [month for month in expected if month not in present],
        "duplicate_months": sorted(
            ordered.loc[ordered["period"].duplicated(keep=False), "period"].astype(str).unique().tolist()
        ),
        "zero_observations": int(values.eq(0).sum()),
        "classification_consistent": ordered["classification"].nunique() == 1 and len(notes) == 1,
        "classification_notes": notes,
        "source_files": source_files,
        "source_change": len(source_files) > 1,
        "outliers_for_review_iqr_rule": outliers,
    }


def build_readiness_audit(repository: DataRepository, root: Path = ROOT) -> dict[str, Any]:
    monthly = repository.monthly.copy()
    monthly["period"] = monthly["period"].astype(str)
    candidates = []
    for disease in PRIMARY_DISEASES:
        subset = monthly.loc[monthly["disease"] == disease]
        for classification, group in subset.groupby("classification", sort=False):
            readiness = series_readiness(group)
            readiness.update({
                "disease": disease,
                "classification": str(classification),
                "observations_are_monthly_reported_cases": True,
            })
            candidates.append(readiness)
    confirmed = monthly.loc[
        monthly["disease"].isin(PRIMARY_DISEASES)
        & monthly["classification"].eq("Confirmed")
    ]
    eligible_diseases = {}
    for disease in PRIMARY_DISEASES:
        series = confirmed.loc[confirmed["disease"] == disease].sort_values("period")
        periods = series["period"].astype(str).tolist()
        holdout_periods = pd.period_range(HOLDOUT_START, HOLDOUT_END, freq="M").astype(str).tolist()
        train_periods = pd.period_range(TRAIN_START, TRAIN_END, freq="M").astype(str).tolist()
        eligible = (
            periods == train_periods + holdout_periods
            and series["classification_note"].nunique() == 1
            and series["classification"].eq("Confirmed").all()
        )
        eligible_diseases[disease] = {
            "eligible_for_limited_2024_holdout": bool(eligible),
            "observations": len(series),
            "training_period": [TRAIN_START, TRAIN_END] if eligible else None,
            "test_period": [HOLDOUT_START, HOLDOUT_END] if eligible else None,
            "reason": (
                "Complete, unique 2023-2024 monthly observations with the same explicit Confirmed category and documentation note."
                if eligible else
                "No complete comparable Confirmed series spans the specified 2023 training and 2024 test periods."
            ),
            "source_files_by_year": {
                year: sorted(
                    series.loc[series["period"].str.startswith(year), "source_file"]
                    .astype(str).unique().tolist()
                )
                for year in ("2023", "2024")
            },
        }
    climate_months = align_climate_features(
        confirmed.loc[confirmed["disease"].eq("Dengue")],
        repository.weather,
    )
    return {
        "experiment_generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_dataset": "data/processed/kerala_disease_monthly_2021_2024.csv",
        "source_sha256": hashlib.sha256(
            (root / "data/processed/kerala_disease_monthly_2021_2024.csv").read_bytes()
        ).hexdigest(),
        "weather_source_sha256": hashlib.sha256(
            (root / "data/processed/kerala_weather_monthly_district_proxy_2021_2024.csv").read_bytes()
        ).hexdigest(),
        "source_columns": [
            "period", "disease", "classification", "classification_note", "cases",
            "source_label", "source_file", "source_page", "source_url",
        ],
        "monthly_dataset_coverage": {
            "first_month": str(monthly["period"].min()),
            "last_month": str(monthly["period"].max()),
            "unique_months": int(monthly["period"].nunique()),
            "records": int(len(monthly)),
        },
        "series": candidates,
        "evaluation": {
            "proposed_2021_2023_train_2024_test_feasible": False,
            "proposed_split_reason": (
                "The 2021 category is status-not-split and the 2022 category is a non-probable category; neither is documented as compatible with explicit Confirmed in 2023-2024."
            ),
            "confirmed_2023_train_2024_test": eligible_diseases,
            "rolling_origin_12_month_horizon_feasible": False,
            "rolling_origin_reason": (
                "Only 24 adjacent, explicitly Confirmed observations are available (2023-2024). "
                "A 12-month initial training period and 12-month horizon yields only one origin, not repeated rolling-origin validation."
            ),
        },
        "annual_district_dataset_used": False,
        "annual_district_dataset_note": (
            "data/processed/kerala_district_annual_disease_2020_2024.csv is annual and excluded from monthly model targets."
        ),
        "2025_annual_surveillance_used": False,
        "2025_annual_surveillance_note": (
            "The separate 2025 DHS annual report remains excluded because monthly comparable case definitions have not been established."
        ),
        "idsp_daily_used": False,
        "idsp_daily_note": (
            "Daily 2026 suspected/confirmed IDSP figures are not merged with the historical monthly classifications."
        ),
        "climate": {
            "weather_dataset": "data/processed/kerala_weather_monthly_district_proxy_2021_2024.csv",
            "columns": [
                "period", "precipitation_sum_mm", "temperature_2m_mean_c",
                "temperature_2m_min_c", "temperature_2m_max_c",
            ],
            "matched_confirmed_disease_months": int(len(climate_months)),
            "weather_scope": "Equal-weight proxy of 14 representative district locations; not population weighted.",
            "climate_model_evaluated": False,
            "reason_not_evaluated": (
                "The compatible training window has only 12 months, insufficient for defensible climate-lag selection or multivariable estimation. "
                "Observed 2024 weather is also not a feature available at a 2023 forecast origin; using it for the 2024 horizon would leak future information."
            ),
        },
    }


def _evaluate_confirmed_series(
    monthly: pd.DataFrame,
    disease: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    series = monthly.loc[
        monthly["disease"].eq(disease) & monthly["classification"].eq("Confirmed")
    ].sort_values("period").reset_index(drop=True)
    if len(series) != 24 or series["period"].astype(str).tolist() != (
        pd.period_range(TRAIN_START, HOLDOUT_END, freq="M").astype(str).tolist()
    ):
        return [], []
    if series["classification_note"].nunique() != 1:
        return [], []
    train, test = chronological_split(
        series,
        train_end=TRAIN_END,
        test_start=HOLDOUT_START,
        test_end=HOLDOUT_END,
    )
    training_values = train["cases"].astype(float).tolist()
    actual = test["cases"].astype(float).tolist()
    model_predictions = {
        "naive": naive_forecast(training_values, len(test)),
        "seasonal_naive": seasonal_naive_forecast(
            training_values, len(test), seasonality=SEASONALITY
        ),
    }
    metric_rows, prediction_rows = [], []
    for model_name, predictions in model_predictions.items():
        metrics = calculate_metrics(
            actual,
            predictions,
            training_values,
            seasonality=SEASONALITY,
        )
        metric_rows.append({
            "disease": disease,
            "classification": "Confirmed",
            "model": model_name,
            **metrics,
            "test_observations": len(actual),
            "training_observations": len(training_values),
            "training_start": TRAIN_START,
            "training_end": TRAIN_END,
            "test_start": HOLDOUT_START,
            "test_end": HOLDOUT_END,
            "mase_note": (
                "Seasonal MASE is undefined: training has no pairs 12 months apart."
                if metrics["mase"] is None
                else "Seasonal MASE scaled by mean absolute 12-month seasonal difference in training only."
            ),
        })
        for period, observed, predicted in zip(test["period"], actual, predictions):
            prediction_rows.append({
                "disease": disease,
                "classification": "Confirmed",
                "period": str(period),
                "model": model_name,
                "actual_cases": observed,
                "predicted_cases": predicted,
                "residual_actual_minus_predicted": observed - predicted,
                "training_start": TRAIN_START,
                "training_end": TRAIN_END,
                "test_start": HOLDOUT_START,
                "test_end": HOLDOUT_END,
            })
    return metric_rows, prediction_rows


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value) if np.isfinite(value) else None
    if pd.isna(value):
        return None
    return value


def _write_readiness_report(audit: dict[str, Any], target: Path) -> None:
    lines = [
        "# Forecasting readiness audit",
        "",
        f"- Generated (UTC): {audit['experiment_generated_at_utc']}",
        f"- Monthly disease source: `{audit['source_dataset']}`",
        f"- Coverage: {audit['monthly_dataset_coverage']['first_month']} to {audit['monthly_dataset_coverage']['last_month']} "
        f"({audit['monthly_dataset_coverage']['unique_months']} months; {audit['monthly_dataset_coverage']['records']} disease/classification records).",
        "- Unit: statewide monthly reported cases; annual district records are excluded.",
        "",
        "## Candidate series coverage",
        "",
        "| Disease | Source classification | Valid observations | Reporting range | Missing months | Duplicate months | Zero cases | IQR flags for review | Source files |",
        "|---|---|---:|---|---:|---:|---:|---|---|",
    ]
    for row in audit["series"]:
        lines.append(
            f"| {row['disease']} | {row['classification']} | {row['valid_observations']} | "
            f"{row['first_reporting_month']} to {row['last_reporting_month']} | "
            f"{len(row['missing_months'])} | {len(row['duplicate_months'])} | "
            f"{row['zero_observations']} | {row['outliers_for_review_iqr_rule']} | "
            f"{'; '.join(row['source_files'])} |"
        )
    lines.extend([
        "",
        "Classifications remain separate: 2021 `reported_category_status_not_split`, 2022 "
        "`non_probable_category_probable_separate`, and 2023–2024 `Confirmed`. The labels and notes do not justify merging 2021 or 2022 into a confirmed-case target. "
        "The 2023 and 2024 confirmed records use different source documents; both explicitly label the monthly case series `Confirmed`, but this document transition is a comparability limitation requiring source review.",
        "",
        "The Tukey 1.5×IQR flags are screening indicators only, not errors or grounds for removal. "
        "In particular, flagged dengue observations in 2021 remain intact and belong to their own unharmonized source category.",
        "",
        "## Evaluation readiness",
        "",
        "The proposed 2021–2023 training / 2024 test is **not feasible as one compatible series**, because the source classifications differ. "
        "For the exact `Confirmed` category, a limited 2023 training / 2024 holdout is complete and unique (12 months in each year) for both diseases. "
        "This one-year holdout is exploratory and cannot establish stable future performance.",
        "",
        audit["evaluation"]["rolling_origin_reason"],
        "",
        "The 2025 annual DHS import, 2026 daily IDSP reports, and annual district panel are excluded. "
        "No monthly values are filled, interpolated, or constructed from annual district totals.",
        "",
        "## Climate feature readiness",
        "",
        f"The monthly weather file aligns on `{audit['climate']['matched_confirmed_disease_months']}` confirmed disease-month records. "
        f"{audit['climate']['weather_scope']} ",
        audit["climate"]["reason_not_evaluated"],
        "",
    ])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")


def _write_experiment_report(
    audit: dict[str, Any],
    metrics: pd.DataFrame,
    target: Path,
) -> None:
    lines = [
        "# Forecasting experiment report",
        "",
        f"- Experiment executed (UTC): {audit['experiment_generated_at_utc']}",
        "- Status: **experimental baseline hindcast only; no operational or future forecasts**",
        "",
        "## Forecasting question and target",
        "",
        "Can simple chronological baselines reproduce monthly statewide reported cases for Dengue and Leptospirosis in 2024, using only each disease's explicitly `Confirmed` 2023 observations?",
        "The target is monthly reported case count (cases), not individual risk, district-month cases, or daily IDSP counts.",
        "",
        "## Data and readiness",
        "",
        f"Input: `{audit['source_dataset']}`; columns used: `period`, `year`, `disease`, `classification`, `classification_note`, `cases`, `source_label`, `source_file`, `source_page`, `source_url`.",
        "Only the 2023–2024 `Confirmed` rows were used in evaluation. The 2021 not-split and 2022 non-probable categories were not combined with Confirmed. The annual 2020–2024 district data, 2025 annual import, and daily 2026 IDSP data were excluded.",
        "Both evaluated series contain 24 valid, unique, consecutive observations: 12 training months (2023) and 12 holdout months (2024). Source documents change from the 2023 source PDF to the 2024 annual IDSP PDF; source labels remain explicitly Confirmed, but the transition is a limitation.",
        "See `reports/forecasting_readiness_audit.md` and `readiness_audit.json` for candidate coverage, missing/duplicate months, zeros, classification notes, source changes, and IQR flags.",
        "",
        "## Baselines and validation",
        "",
        "- Naïve: repeat December 2023's observed value for all 2024 months.",
        "- Seasonal naïve: repeat each corresponding 2023 calendar-month value into 2024.",
        "- Chronological split: train January–December 2023; test January–December 2024. No random split or future-fitted preprocessing is used.",
        "- The requested January 2021–December 2023 train interval is not compatible with a single target because classifications change in 2021, 2022, and 2023.",
        f"- {audit['evaluation']['rolling_origin_reason']}",
        "",
        "MAE is mean absolute error in reported cases. RMSE is the square root of mean squared error in reported cases and penalizes large misses more. MASE is scaled absolute error; this report uses a 12-month seasonal training scale. It is undefined when training lacks 12-month-separated pairs or the scale is zero. Here the training window contains only one seasonal cycle, so MASE is reported as unavailable rather than replaced with a different scale.",
        "",
        "## Results",
        "",
        "| Disease | Classification | Model | Test months | MAE (cases) | RMSE (cases) | Seasonal MASE |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for row in metrics.to_dict(orient="records"):
        mase = "Not estimable" if pd.isna(row["mase"]) else f"{row['mase']:.3f}"
        lines.append(
            f"| {row['disease']} | {row['classification']} | {row['model']} | "
            f"{row['test_observations']} | {row['mae']:.3f} | {row['rmse']:.3f} | {mase} |"
        )
    lines.extend([
        "",
        "Metrics are based on one 12-month test year and should not be interpreted as evidence that either baseline is reliable for future years.",
        "",
        "## Climate feature investigation",
        "",
        f"The weather proxy aligns with {audit['climate']['matched_confirmed_disease_months']} confirmed disease-months, but no climate-augmented model was fitted or scored. {audit['climate']['reason_not_evaluated']} No lag was selected using the holdout, and no causal inference is made.",
        "",
        "## Interpretation, limitations, and decision",
        "",
        "This run supplies a reproducible 2024 baseline comparison and actual-versus-predicted values, not a validated production forecasting model. Performance is sensitive to one holdout year, the training sample is one seasonal cycle, and source-document comparability across 2023–2024 should be reviewed. The historical weather proxy is not a forecast feed.",
        "",
        "**Decision: future forecasting is not yet scientifically justified for operational use.** The 2024 results may be inspected as a limited retrospective experiment; no future predictions, risk scores, outbreak alerts, or hospital-capacity outputs are published.",
        "",
        "Outputs are stored in `reports/forecasting_experiment/`; charts are stored in `reports/figures/forecasting_*.png`.",
        "",
    ])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")


def _create_plots(
    root: Path,
    monthly: pd.DataFrame,
    predictions: pd.DataFrame,
    metrics: pd.DataFrame,
) -> list[str]:
    directory = root / FIGURE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    produced = []
    for disease in PRIMARY_DISEASES:
        observed = monthly.loc[
            monthly["disease"].eq(disease) & monthly["classification"].eq("Confirmed")
        ].sort_values("period")
        predicted = predictions.loc[predictions["disease"].eq(disease)]
        if predicted.empty:
            continue
        fig, axis = plt.subplots(figsize=(10, 4.5))
        axis.plot(observed["period"], observed["cases"], color="#245c4b", marker="o", label="Observed")
        for model in BASELINE_NAMES:
            part = predicted.loc[predicted["model"].eq(model)]
            axis.plot(part["period"], part["predicted_cases"], marker=".", label=model.replace("_", " ").title())
        axis.axvline(HOLDOUT_START, color="#888888", linestyle="--", linewidth=1)
        axis.set_title(f"{disease} confirmed monthly cases · experimental 2024 holdout")
        axis.set_xlabel("Reporting month")
        axis.set_ylabel("Reported cases")
        axis.tick_params(axis="x", rotation=45)
        axis.legend()
        fig.tight_layout()
        filename = f"forecasting_{disease.casefold()}_actual_vs_predicted.png"
        fig.savefig(directory / filename, dpi=140)
        plt.close(fig)
        produced.append(f"reports/figures/{filename}")

        residuals = predicted.pivot(index="period", columns="model", values="residual_actual_minus_predicted")
        fig, axis = plt.subplots(figsize=(10, 4))
        for model in BASELINE_NAMES:
            if model in residuals:
                axis.plot(residuals.index, residuals[model], marker="o", label=model.replace("_", " ").title())
        axis.axhline(0, color="#777777", linewidth=1)
        axis.set_title(f"{disease} holdout residuals · actual minus predicted")
        axis.set_xlabel("Reporting month")
        axis.set_ylabel("Residual cases")
        axis.tick_params(axis="x", rotation=45)
        axis.legend()
        fig.tight_layout()
        filename = f"forecasting_{disease.casefold()}_residuals.png"
        fig.savefig(directory / filename, dpi=140)
        plt.close(fig)
        produced.append(f"reports/figures/{filename}")

    fig, axis = plt.subplots(figsize=(8, 4.5))
    for disease in PRIMARY_DISEASES:
        subset = metrics.loc[metrics["disease"].eq(disease)]
        positions = np.arange(len(subset)) + (0.18 if disease == "Dengue" else -0.18)
        axis.bar(positions, subset["mae"], width=0.34, label=disease)
    axis.set_xticks(np.arange(len(BASELINE_NAMES)), [name.replace("_", " ").title() for name in BASELINE_NAMES])
    axis.set_ylabel("MAE (reported cases)")
    axis.set_title("2024 holdout baseline error comparison")
    axis.legend()
    fig.tight_layout()
    filename = "forecasting_baseline_error_comparison.png"
    fig.savefig(directory / filename, dpi=140)
    plt.close(fig)
    produced.append(f"reports/figures/{filename}")
    return produced


def run_experiment(root: Path = ROOT) -> dict[str, Any]:
    repository = DataRepository.load(root)
    audit = build_readiness_audit(repository, root)
    monthly = repository.monthly.copy()
    monthly["period"] = monthly["period"].astype(str)
    metric_rows, prediction_rows = [], []
    for disease in PRIMARY_DISEASES:
        disease_metrics, disease_predictions = _evaluate_confirmed_series(monthly, disease)
        metric_rows.extend(disease_metrics)
        prediction_rows.extend(disease_predictions)
    if not metric_rows:
        raise ForecastExperimentError("No compatible, complete confirmed series passed the evaluation gate.")

    metrics = pd.DataFrame(metric_rows)
    predictions = pd.DataFrame(prediction_rows)
    experiment_dir = root / EXPERIMENT_DIR
    experiment_dir.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(experiment_dir / "evaluation_metrics.csv", index=False)
    predictions.to_csv(experiment_dir / "actual_vs_predicted.csv", index=False)
    predictions[
        [
            "disease", "classification", "period", "model",
            "residual_actual_minus_predicted", "training_start", "training_end",
            "test_start", "test_end",
        ]
    ].to_csv(experiment_dir / "forecast_residuals.csv", index=False)
    _write_readiness_report(audit, root / READINESS_REPORT)

    figures = _create_plots(root, monthly, predictions, metrics)
    config = {
        "experiment_generated_at_utc": audit["experiment_generated_at_utc"],
        "target": "statewide monthly reported cases",
        "dataset": "data/processed/kerala_disease_monthly_2021_2024.csv",
        "source_sha256": audit["source_sha256"],
        "weather_source_sha256": audit["weather_source_sha256"],
        "columns": audit["source_columns"],
        "diseases": list(PRIMARY_DISEASES),
        "classification": "Confirmed",
        "training_period": [TRAIN_START, TRAIN_END],
        "test_period": [HOLDOUT_START, HOLDOUT_END],
        "baselines": {
            "naive": "Repeat the final observed training value for each test month.",
            "seasonal_naive": "Repeat the corresponding month from the latest complete training year.",
        },
        "seasonality": SEASONALITY,
        "metric_scaling": "Seasonal MASE denominator uses training pairs separated by 12 months.",
        "preprocessing_fit_scope": "No data-fitted preprocessing.",
        "climate_features_in_model": False,
        "operational_forecasting_available": False,
        "validity_gate": (
            "Complete unique monthly Confirmed observations spanning Jan 2023-Dec 2024, "
            "12 train and 12 test months, and one consistent classification note."
        ),
        "figures": figures,
    }
    (experiment_dir / "model_config.json").write_text(
        json.dumps(_json_safe(config), indent=2) + "\n",
        encoding="utf-8",
    )
    audit["figures"] = figures
    audit["evaluation_metrics"] = _json_safe(metric_rows)
    audit["actual_vs_predicted"] = _json_safe(prediction_rows)
    audit["status"] = "experimental_baseline_hindcast"
    audit["validity_checks_passed"] = True
    audit["future_forecasts_available"] = False
    audit["climate_features_improved_performance"] = None
    audit["climate_feature_comparison_status"] = (
        "Not evaluated; insufficient compatible training history and future climate availability."
    )
    (experiment_dir / "experiment.json").write_text(
        json.dumps(_json_safe(audit), indent=2) + "\n",
        encoding="utf-8",
    )
    _write_experiment_report(audit, metrics, root / EXPERIMENT_REPORT)
    return _json_safe(audit)


def load_experiment_artifact(root: Path = ROOT) -> dict[str, Any]:
    artifact_path = root / EXPERIMENT_DIR / "experiment.json"
    source_paths = {
        "source_sha256": root / "data/processed/kerala_disease_monthly_2021_2024.csv",
        "weather_source_sha256": root / "data/processed/kerala_weather_monthly_district_proxy_2021_2024.csv",
    }
    try:
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        current_digests = {
            key: hashlib.sha256(path.read_bytes()).hexdigest()
            for key, path in source_paths.items()
        }
    except (OSError, json.JSONDecodeError) as exc:
        raise ForecastExperimentError(
            "Forecasting experiment artifacts are unavailable; run the documented experiment command."
        ) from exc
    if any(artifact.get(key) != digest for key, digest in current_digests.items()):
        raise ForecastExperimentError(
            "Forecasting experiment artifacts do not match the current monthly disease/weather inputs; rerun the experiment."
        )
    return artifact
