"""Post-hoc conformal interval calibration for saved district-month forecasts.

Only forecast errors from EARLIER origins are used to calibrate a given origin.
Calibration can widen or narrow intervals; it cannot fix a biased forecast mean.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

GROUP_KEYS = ("disease", "model_name", "feature_set", "horizon")
LEVELS = {"80": 0.80, "95": 0.95}
MIN_WIDTH = 1.0
MIN_SHRINK = -0.49
REQUIRED_COLUMNS = {
    "disease", "model_name", "feature_set", "horizon", "validation_phase",
    "origin_period", "actual",
    "prediction_interval_80_lower", "prediction_interval_80_upper",
    "prediction_interval_95_lower", "prediction_interval_95_upper",
}


def relative_interval_scores(actual, lower, upper) -> np.ndarray:
    """Distance outside the interval divided by its width (negative if inside)."""
    actual = np.asarray(actual, dtype=float)
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    width = np.maximum(upper - lower, MIN_WIDTH)
    return np.maximum(lower - actual, actual - upper) / width


def conformal_quantile(scores, coverage: float, min_scores: int) -> float:
    """Finite-sample conformal quantile; NaN when there is too little evidence."""
    values = np.asarray(scores, dtype=float)
    values = np.sort(values[np.isfinite(values)])
    n = len(values)
    if n < min_scores:
        return float("nan")
    rank = math.ceil(round((n + 1) * coverage, 9))
    if rank > n:
        return float("nan")
    return max(float(values[rank - 1]), MIN_SHRINK)


def calibrate_predictions(predictions: pd.DataFrame, *, min_scores: int = 28) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(predictions.columns)
    if missing:
        raise ValueError(f"Predictions are missing columns: {sorted(missing)}")
    frame = predictions.copy().reset_index(drop=True)
    for level in LEVELS:
        frame[f"cal_{level}_lower"] = np.nan
        frame[f"cal_{level}_upper"] = np.nan
        frame[f"calibration_q{level}"] = np.nan
    frame["calibration_n_scores"] = 0
    for _, group in frame.groupby(list(GROUP_KEYS), sort=False):
        history = group[group["validation_phase"].eq("rolling_origin")]
        for origin, rows in group.groupby("origin_period"):
            prior = history[history["origin_period"] < origin]
            frame.loc[rows.index, "calibration_n_scores"] = len(prior)
            for level, coverage in LEVELS.items():
                lo_col = f"prediction_interval_{level}_lower"
                hi_col = f"prediction_interval_{level}_upper"
                scores = relative_interval_scores(
                    prior["actual"], prior[lo_col], prior[hi_col]
                )
                q = conformal_quantile(scores, coverage, min_scores)
                frame.loc[rows.index, f"calibration_q{level}"] = q
                if np.isnan(q):
                    continue
                lower = rows[lo_col].to_numpy(dtype=float)
                upper = rows[hi_col].to_numpy(dtype=float)
                width = np.maximum(upper - lower, MIN_WIDTH)
                mid = (lower + upper) / 2
                new_lower = np.minimum(np.maximum(0.0, lower - q * width), mid)
                new_upper = np.maximum(upper + q * width, mid)
                frame.loc[rows.index, f"cal_{level}_lower"] = new_lower
                frame.loc[rows.index, f"cal_{level}_upper"] = new_upper
    return frame


def summarize_calibration(calibrated: pd.DataFrame) -> pd.DataFrame:
    """Coverage and width before/after, on the SAME rows that could be calibrated."""
    keys = ["disease", "model_name", "feature_set", "validation_phase", "horizon"]
    rows = []
    for key, group in calibrated.groupby(keys, sort=True):
        record = dict(zip(keys, key))
        any_usable = False
        for level in LEVELS:
            usable = group.dropna(subset=[f"cal_{level}_lower"])
            record[f"n_{level}"] = int(len(usable))
            if usable.empty:
                for name in ("coverage_before", "coverage_after", "width_before", "width_after"):
                    record[f"{name}_{level}"] = np.nan
                continue
            any_usable = True
            actual = usable["actual"]
            lo0 = usable[f"prediction_interval_{level}_lower"]
            hi0 = usable[f"prediction_interval_{level}_upper"]
            lo1 = usable[f"cal_{level}_lower"]
            hi1 = usable[f"cal_{level}_upper"]
            record[f"coverage_before_{level}"] = float(((actual >= lo0) & (actual <= hi0)).mean())
            record[f"coverage_after_{level}"] = float(((actual >= lo1) & (actual <= hi1)).mean())
            record[f"width_before_{level}"] = float((hi0 - lo0).mean())
            record[f"width_after_{level}"] = float((hi1 - lo1).mean())
        if any_usable:
            rows.append(record)
    return pd.DataFrame(rows)
