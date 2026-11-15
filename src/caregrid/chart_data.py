"""Chart-ready tables for the dashboard (exploratory; backtest forecasts only).

All rows are backtest forecasts compared with known actuals, not future forecasts.
Calibrated bands are a candidate adjustment from earlier origins only; they do not
fix biased forecast means. No model is ranked or declared best here: MAE must be
read together with interval coverage.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

KEY_COLUMNS = ["model_name", "feature_set", "disease", "district", "origin_period", "target_period"]
ORIG_COLUMNS = [
    "prediction_interval_80_lower", "prediction_interval_80_upper",
    "prediction_interval_95_lower", "prediction_interval_95_upper",
]
CAL_COLUMNS = ["cal_80_lower", "cal_80_upper", "cal_95_lower", "cal_95_upper", "calibration_n_scores"]
REQUIRED = KEY_COLUMNS + ["horizon", "validation_phase", "actual", "predictive_mean"] + ORIG_COLUMNS
EVIDENCE_ROLE = {
    "rolling_origin": "development_rolling_origin",
    "final_2025": "holdout_descriptive_only",
}
EXPLORATORY_LABEL = "backtest_forecast_exploratory_not_a_future_forecast"
DISPLAY_COLUMNS = [f"display_{lvl}_{side}" for lvl in ("80", "95") for side in ("lower", "upper")]
OUTPUT_COLUMNS = (
    KEY_COLUMNS
    + ["horizon", "validation_phase", "evidence_role", "actual", "predictive_mean"]
    + ORIG_COLUMNS
    + CAL_COLUMNS
    + ["band_source_80", "band_source_95"]
    + DISPLAY_COLUMNS
    + ["caution_poisson_intervals_too_narrow", "caution_dengue_horizon_9_12_undercoverage", "exploratory_label"]
)


def _prepare(df: pd.DataFrame, name: str) -> pd.DataFrame:
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"{name} is missing columns: {missing}")
    out = df[REQUIRED + [c for c in CAL_COLUMNS if c in df.columns]].copy()
    for c in CAL_COLUMNS:
        if c not in out.columns:
            out[c] = np.nan
    return out


def build_forecast_band_table(calibrated: pd.DataFrame, direct: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per forecast, with original bands, calibrated bands (where they exist) and display bands."""
    parts = [_prepare(calibrated, "calibrated")]
    if direct is not None:
        parts.append(_prepare(direct, "direct"))
    out = pd.concat(parts, ignore_index=True)
    if out.duplicated(KEY_COLUMNS).any():
        raise ValueError("duplicate forecast keys across the input tables.")
    unknown = sorted(set(out["validation_phase"]) - set(EVIDENCE_ROLE))
    if unknown:
        raise ValueError(f"unknown validation_phase values: {unknown}")
    out["evidence_role"] = out["validation_phase"].map(EVIDENCE_ROLE)
    out["horizon"] = out["horizon"].astype(int)

    has80 = out["cal_80_lower"].notna() & out["cal_80_upper"].notna()
    has95 = out["cal_95_lower"].notna() & out["cal_95_upper"].notna()
    out["band_source_80"] = np.where(has80, "calibrated", "original")
    out["band_source_95"] = np.where(has95, "calibrated", "original")
    for level, has in (("80", has80), ("95", has95)):
        for side in ("lower", "upper"):
            out[f"display_{level}_{side}"] = np.where(
                has, out[f"cal_{level}_{side}"], out[f"prediction_interval_{level}_{side}"]
            )
    out["calibration_n_scores"] = out["calibration_n_scores"].fillna(0).astype(int)

    out["caution_poisson_intervals_too_narrow"] = out["model_name"].eq("poisson_regression")
    out["caution_dengue_horizon_9_12_undercoverage"] = out["disease"].eq("Dengue") & out["horizon"].ge(9)
    out["exploratory_label"] = EXPLORATORY_LABEL
    return out[OUTPUT_COLUMNS].sort_values(KEY_COLUMNS).reset_index(drop=True)


def _covered(actual: pd.Series, lower: pd.Series, upper: pd.Series) -> pd.Series:
    """Inclusive interval coverage as 0.0/1.0."""
    return ((actual >= lower) & (actual <= upper)).astype(float)


def build_model_comparison(bands: pd.DataFrame) -> pd.DataFrame:
    """MAE, RMSE, coverage and width per model, disease, evidence role and horizon (plus pooled).

    Deliberately has no rank or best-model column.
    """
    b = bands.copy()
    b["abs_error"] = (b["actual"] - b["predictive_mean"]).abs()
    b["sq_error"] = (b["actual"] - b["predictive_mean"]) ** 2
    for lvl in ("80", "95"):
        lo, hi = f"prediction_interval_{lvl}_lower", f"prediction_interval_{lvl}_upper"
        dlo, dhi = f"display_{lvl}_lower", f"display_{lvl}_upper"
        b[f"cov_orig_{lvl}"] = _covered(b["actual"], b[lo], b[hi])
        b[f"cov_disp_{lvl}"] = _covered(b["actual"], b[dlo], b[dhi])
        b[f"width_orig_{lvl}"] = b[hi] - b[lo]
        b[f"width_disp_{lvl}"] = b[dhi] - b[dlo]
    b["horizon_scope"] = "h" + b["horizon"].astype(str)
    pooled = b.copy()
    pooled["horizon_scope"] = "pooled"
    both = pd.concat([b, pooled], ignore_index=True)

    group = both.groupby(
        ["disease", "model_name", "feature_set", "evidence_role", "horizon_scope"], sort=True
    )
    out = group.agg(
        n_forecasts=("actual", "size"),
        mae=("abs_error", "mean"),
        rmse=("sq_error", lambda s: float(np.sqrt(s.mean()))),
        coverage_80_original=("cov_orig_80", "mean"),
        coverage_95_original=("cov_orig_95", "mean"),
        coverage_80_display=("cov_disp_80", "mean"),
        coverage_95_display=("cov_disp_95", "mean"),
        mean_width_80_original=("width_orig_80", "mean"),
        mean_width_80_display=("width_disp_80", "mean"),
        share_80_calibrated=("band_source_80", lambda s: float((s == "calibrated").mean())),
        caution_poisson_intervals_too_narrow=("caution_poisson_intervals_too_narrow", "max"),
        caution_dengue_horizon_9_12_undercoverage=("caution_dengue_horizon_9_12_undercoverage", "max"),
    ).reset_index()
    out["horizon"] = pd.to_numeric(out["horizon_scope"].str[1:], errors="coerce")
    return out
