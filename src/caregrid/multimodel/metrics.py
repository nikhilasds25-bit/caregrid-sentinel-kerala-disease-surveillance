"""Metrics for retrospective district-month count forecasts."""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


GROUP_COLUMNS = (
    "disease",
    "model_name",
    "feature_set",
    "validation_phase",
    "horizon",
)


def poisson_deviance(actual: Iterable[float], predicted: Iterable[float]) -> np.ndarray:
    observed = np.asarray(list(actual), dtype=float)
    mean = np.maximum(np.asarray(list(predicted), dtype=float), 1e-12)
    terms = np.where(
        observed > 0,
        observed * np.log(np.maximum(observed, 1e-12) / mean) - (observed - mean),
        mean,
    )
    return 2 * terms


def calculate_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    """Return overall and district-stratified metrics with unavailable scores as NaN."""
    if predictions.empty:
        return pd.DataFrame()
    rows = []
    groupings = [list(GROUP_COLUMNS), [*GROUP_COLUMNS, "district"]]
    for columns in groupings:
        for key, group in predictions.groupby(columns, dropna=False, sort=True):
            key = key if isinstance(key, tuple) else (key,)
            actual = group["actual"].to_numpy(dtype=float)
            predicted = group["predictive_mean"].to_numpy(dtype=float)
            residual = actual - predicted
            lower80 = group["prediction_interval_80_lower"].to_numpy(dtype=float)
            upper80 = group["prediction_interval_80_upper"].to_numpy(dtype=float)
            lower95 = group["prediction_interval_95_lower"].to_numpy(dtype=float)
            upper95 = group["prediction_interval_95_upper"].to_numpy(dtype=float)
            log_scores = group["predictive_log_score"].dropna()
            record = dict(zip(columns, key))
            record.update({
                "scope": "district" if "district" in columns else "pooled_district_months",
                "n_predictions": int(len(group)),
                "mae": float(np.mean(np.abs(residual))),
                "rmse": float(np.sqrt(np.mean(np.square(residual)))),
                "mean_poisson_deviance": float(np.mean(poisson_deviance(actual, predicted))),
                "mean_predictive_log_score": (
                    float(log_scores.mean()) if len(log_scores) else np.nan
                ),
                "coverage_80": float(np.mean((actual >= lower80) & (actual <= upper80))),
                "mean_width_80": float(np.mean(upper80 - lower80)),
                "coverage_95": float(np.mean((actual >= lower95) & (actual <= upper95))),
                "mean_width_95": float(np.mean(upper95 - lower95)),
            })
            rows.append(record)
    return pd.DataFrame(rows)
