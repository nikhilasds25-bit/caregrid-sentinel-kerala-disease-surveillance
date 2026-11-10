"""Common scoring and alignment checks for saved retrospective forecasts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


PREDICTION_COLUMNS = (
    "model_name",
    "model_version",
    "disease",
    "classification",
    "district",
    "geographic_level",
    "origin_period",
    "target_period",
    "horizon",
    "actual",
    "predictive_mean",
    "predictive_variance",
    "prediction_interval_80_lower",
    "prediction_interval_80_upper",
    "prediction_interval_95_lower",
    "prediction_interval_95_upper",
    "predictive_log_score",
    "feature_set",
    "validation_phase",
    "validation_window_id",
)
OBSERVATION_KEYS = (
    "disease",
    "classification",
    "geographic_level",
    "validation_phase",
    "validation_window_id",
    "origin_period",
    "target_period",
    "district",
    "horizon",
)
CANDIDATE_KEYS = ("model_name", "model_version", "feature_set")


@dataclass(frozen=True)
class EvaluationResult:
    overall_metrics: pd.DataFrame
    fold_metrics: pd.DataFrame
    residuals: pd.DataFrame


def load_prediction_file(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Prediction output is missing: {path}")
    return pd.read_csv(path)


def validate_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(set(PREDICTION_COLUMNS) - set(predictions.columns))
    if missing:
        raise ValueError(f"Prediction data is missing columns: {missing}")
    data = predictions.copy()
    if data.empty:
        raise ValueError("Prediction data is empty.")
    if data[list(PREDICTION_COLUMNS)].isna().any().any():
        optional = {
            "model_version",
            "predictive_variance",
            "prediction_interval_80_lower",
            "prediction_interval_80_upper",
            "prediction_interval_95_lower",
            "prediction_interval_95_upper",
            "predictive_log_score",
        }
        required = [column for column in PREDICTION_COLUMNS if column not in optional]
        if data[required].isna().any().any():
            raise ValueError("Prediction records have missing required identifiers or values.")
    numeric_columns = (
        "horizon",
        "actual",
        "predictive_mean",
        "prediction_interval_80_lower",
        "prediction_interval_80_upper",
        "prediction_interval_95_lower",
        "prediction_interval_95_upper",
        "predictive_log_score",
    )
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    if data[["actual", "predictive_mean"]].isna().any().any():
        raise ValueError("Actual and predicted means must be present for every record.")
    if not np.isfinite(data[["actual", "predictive_mean"]].to_numpy(dtype=float)).all():
        raise ValueError("Actual and predicted means must be finite.")
    if (data["actual"] < 0).any() or (data["predictive_mean"] < 0).any():
        raise ValueError("Count observations and predictions must be non-negative.")
    if "predictive_variance" in data and (
        pd.to_numeric(data["predictive_variance"], errors="coerce").dropna() < 0
    ).any():
        raise ValueError("Predictive variance must be non-negative when available.")
    if (data["horizon"] < 1).any():
        raise ValueError("Forecast horizons must be positive.")
    key = [*OBSERVATION_KEYS, *CANDIDATE_KEYS]
    if data.duplicated(key).any():
        raise ValueError("Duplicate model prediction keys were found.")
    for level in (80, 95):
        lower = data[f"prediction_interval_{level}_lower"]
        upper = data[f"prediction_interval_{level}_upper"]
        valid = lower.notna() & upper.notna()
        if (lower[valid] < 0).any():
            raise ValueError(f"{level}% count prediction interval has a negative lower bound.")
        if (lower[valid] > upper[valid]).any():
            raise ValueError(f"{level}% prediction interval lower bound exceeds upper bound.")
    return data


def validate_equivalent_observations(predictions: pd.DataFrame) -> int:
    """Require every model/feature candidate to score the same actual observations."""
    data = validate_predictions(predictions)
    if data["validation_phase"].nunique() > 2:
        raise ValueError("Unexpected validation phase values.")
    comparison_groups = ["disease", "validation_phase", "horizon"]
    for group_key, group in data.groupby(comparison_groups, sort=False, dropna=False):
        candidates = group.groupby(list(CANDIDATE_KEYS), sort=False, dropna=False)
        candidate_sets: list[tuple[tuple[str, str], dict[tuple[object, ...], float]]] = []
        for candidate, candidate_frame in candidates:
            if not isinstance(candidate, tuple):
                candidate = (candidate,)
            observations = {
                tuple(row[column] for column in OBSERVATION_KEYS): float(row["actual"])
                for _, row in candidate_frame.iterrows()
            }
            candidate_sets.append(
                ((str(candidate[0]), str(candidate[1]), str(candidate[2])), observations)
            )
        if len(candidate_sets) < 2:
            continue
        reference_name, reference = candidate_sets[0]
        for candidate_name, observations in candidate_sets[1:]:
            if observations.keys() != reference.keys():
                raise ValueError(
                    f"Unequal validation observations for {group_key}: "
                    f"{reference_name} versus {candidate_name}."
                )
            if any(
                not np.isclose(reference[key], observations[key], equal_nan=False)
                for key in reference
            ):
                raise ValueError(
                    f"Observed values differ across candidates for {group_key}: "
                    f"{reference_name} versus {candidate_name}."
                )
    return len(data)


def _poisson_deviance(actual: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    mean = np.maximum(predicted, 1e-12)
    terms = np.where(
        actual > 0,
        actual * np.log(np.maximum(actual, 1e-12) / mean) - (actual - mean),
        mean,
    )
    return 2 * terms


def _interval_score(
    actual: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    alpha: float,
) -> np.ndarray:
    score = upper - lower
    score += (2 / alpha) * np.maximum(lower - actual, 0)
    score += (2 / alpha) * np.maximum(actual - upper, 0)
    return score


def _metrics_for_group(
    group: pd.DataFrame,
    key: dict[str, object],
    scope: str,
) -> dict[str, object]:
    actual = group["actual"].to_numpy(dtype=float)
    predicted = group["predictive_mean"].to_numpy(dtype=float)
    residual = actual - predicted
    record: dict[str, object] = {
        **key,
        "scope": scope,
        "n_predictions": int(len(group)),
        "mae": float(np.mean(np.abs(residual))),
        "rmse": float(np.sqrt(np.mean(np.square(residual)))),
        "mean_poisson_deviance": float(np.mean(_poisson_deviance(actual, predicted))),
        "mean_predictive_log_score": (
            float(group["predictive_log_score"].mean())
            if group["predictive_log_score"].notna().any()
            else np.nan
        ),
    }
    for level, alpha in ((80, 0.20), (95, 0.05)):
        lower = group[f"prediction_interval_{level}_lower"].to_numpy(dtype=float)
        upper = group[f"prediction_interval_{level}_upper"].to_numpy(dtype=float)
        valid = np.isfinite(lower) & np.isfinite(upper)
        if valid.any():
            record[f"coverage_{level}"] = float(
                np.mean((actual[valid] >= lower[valid]) & (actual[valid] <= upper[valid]))
            )
            record[f"mean_width_{level}"] = float(np.mean(upper[valid] - lower[valid]))
            record[f"interval_score_{level}"] = float(
                np.mean(_interval_score(actual[valid], lower[valid], upper[valid], alpha))
            )
            record[f"n_interval_{level}"] = int(valid.sum())
        else:
            record[f"coverage_{level}"] = np.nan
            record[f"mean_width_{level}"] = np.nan
            record[f"interval_score_{level}"] = np.nan
            record[f"n_interval_{level}"] = 0
    return record


def evaluate_predictions(predictions: pd.DataFrame) -> EvaluationResult:
    """Score pooled and district strata and produce origin-level stability metrics."""
    data = validate_predictions(predictions)
    validate_equivalent_observations(data)
    group_columns = [
        "disease",
        "model_name",
        "feature_set",
        "validation_phase",
        "horizon",
    ]
    records: list[dict[str, object]] = []
    for group_key, group in data.groupby(group_columns, sort=True, dropna=False):
        values = dict(zip(group_columns, group_key))
        records.append(_metrics_for_group(group, values, "pooled_district_months"))
        for district, district_frame in group.groupby("district", sort=True):
            records.append(
                _metrics_for_group(
                    district_frame,
                    {**values, "district": district},
                    "district",
                )
            )
    fold_columns = [
        "disease",
        "model_name",
        "feature_set",
        "validation_phase",
        "validation_window_id",
        "horizon",
    ]
    fold_records = []
    for group_key, group in data.groupby(fold_columns, sort=True, dropna=False):
        values = dict(zip(fold_columns, group_key))
        fold_records.append(_metrics_for_group(group, values, "validation_window"))
    residuals = data.copy()
    residuals["residual"] = residuals["actual"] - residuals["predictive_mean"]
    residuals["absolute_error"] = residuals["residual"].abs()
    residuals["squared_error"] = residuals["residual"].pow(2)
    for level in (80, 95):
        lower = residuals[f"prediction_interval_{level}_lower"]
        upper = residuals[f"prediction_interval_{level}_upper"]
        residuals[f"interval_hit_{level}"] = (
            (residuals["actual"] >= lower) & (residuals["actual"] <= upper)
        ).where(lower.notna() & upper.notna())
    return EvaluationResult(
        overall_metrics=pd.DataFrame.from_records(records),
        fold_metrics=pd.DataFrame.from_records(fold_records),
        residuals=residuals,
    )


def uncertainty_review(
    predictions: pd.DataFrame,
    *,
    phases: tuple[str, ...] = ("rolling_origin", "final_2025"),
) -> pd.DataFrame:
    """Summarize interval coverage, widths, and under/overcoverage by horizon."""
    data = validate_predictions(predictions)
    data = data[data["validation_phase"].isin(phases)]
    group_columns = [
        "disease",
        "model_name",
        "feature_set",
        "validation_phase",
        "horizon",
    ]
    rows = []
    for group_key, group in data.groupby(group_columns, sort=True, dropna=False):
        row = dict(zip(group_columns, group_key))
        row["n_predictions"] = len(group)
        row["n_origins"] = group["validation_window_id"].nunique()
        for level, nominal in ((80, 0.80), (95, 0.95)):
            lower = group[f"prediction_interval_{level}_lower"]
            upper = group[f"prediction_interval_{level}_upper"]
            valid = lower.notna() & upper.notna()
            coverage = (
                float(((group.loc[valid, "actual"] >= lower[valid])
                       & (group.loc[valid, "actual"] <= upper[valid])).mean())
                if valid.any() else np.nan
            )
            width = float((upper[valid] - lower[valid]).mean()) if valid.any() else np.nan
            row[f"coverage_{level}"] = coverage
            row[f"nominal_{level}"] = nominal
            row[f"coverage_gap_{level}"] = coverage - nominal if valid.any() else np.nan
            row[f"mean_width_{level}"] = width
            lower_tolerance = nominal - 0.10
            upper_tolerance = min(1.0, nominal + 0.10)
            row[f"coverage_assessment_{level}"] = (
                "unavailable"
                if not valid.any()
                else (
                    "undercoverage"
                    if coverage < lower_tolerance
                    else (
                        "overcoverage"
                        if coverage > upper_tolerance
                        else "within_10_percentage_point_tolerance"
                    )
                )
            )
        rows.append(row)
    return pd.DataFrame(rows)
