"""Exploratory Q90 exceedance thresholds and exceedance probabilities.

These are EXPLORATORY STATISTICAL THRESHOLDS, not official outbreak definitions.
An exceedance (observed count strictly greater than the threshold) is NOT a
confirmed outbreak. Replace or refine once an epidemiologically validated
definition is supplied.

Methods (per disease and district, Confirmed counts only):
  q90_all_months    : quantile over ALL calendar months up to the origin.
  q90_season_window : quantile over the target calendar month +/- season_half_width
                      months (circular), up to the origin. Sensitivity analysis for
                      normal seasonal peaks.
Leakage control: only observations with period <= origin enter a threshold.
Quantile: numpy 'linear' interpolation. Exceedance: strictly greater than.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from caregrid.model_intelligence.interfaces import OutbreakProbabilityRecord

METHOD_ALL = "q90_all_months"
METHOD_SEASON = "q90_season_window"
DEFINITION_IDS = {
    METHOD_ALL: "exploratory_q90_all_months_v1",
    METHOD_SEASON: "exploratory_q90_season_window_v1",
}
THRESHOLD_LABEL = "exploratory_statistical_threshold_not_an_outbreak_definition"
CALIBRATION_STATUS = "uncalibrated_exploratory"
REQUIRED_COLUMNS = ("disease", "district", "period", "cases")


def _validate(observations: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in observations.columns]
    if missing:
        raise ValueError(f"observations is missing columns: {missing}")
    if observations.duplicated(["disease", "district", "period"]).any():
        raise ValueError("observations contain duplicate disease/district/period rows.")
    if observations["cases"].isna().any() or (observations["cases"] < 0).any():
        raise ValueError("observations contain missing or negative case counts.")


def compute_thresholds(
    observations: pd.DataFrame,
    *,
    origin: str,
    quantile: float = 0.90,
    season_half_width: int = 1,
    min_values_all_months: int = 24,
    min_values_season: int = 20,
) -> pd.DataFrame:
    """Thresholds for every disease/district/target calendar month, using period <= origin."""
    _validate(observations)
    ref = observations[observations["period"] <= origin]
    if ref.empty:
        raise ValueError(f"No observations on or before origin {origin}.")
    rows: list[dict] = []
    for (disease, district), grp in ref.groupby(["disease", "district"], sort=True):
        periods = grp["period"].to_numpy()
        cases = grp["cases"].to_numpy(dtype=float)
        cal = np.array([int(p[5:7]) for p in periods])
        for method in (METHOD_ALL, METHOD_SEASON):
            for m in range(1, 13):
                if method == METHOD_ALL:
                    mask = np.ones(len(cases), dtype=bool)
                    minimum, half = min_values_all_months, np.nan
                else:
                    dist = np.abs(cal - m)
                    mask = np.minimum(dist, 12 - dist) <= season_half_width
                    minimum, half = min_values_season, season_half_width
                vals = cases[mask]
                ok = len(vals) >= minimum
                rows.append(
                    {
                        "disease": disease,
                        "district": district,
                        "method": method,
                        "threshold_definition_id": DEFINITION_IDS[method],
                        "threshold_label": THRESHOLD_LABEL,
                        "origin_period": origin,
                        "reference_start": periods[mask].min() if len(vals) else None,
                        "reference_end": periods[mask].max() if len(vals) else None,
                        "target_calendar_month": m,
                        "n_reference_values": int(len(vals)),
                        "min_reference_values": minimum,
                        "quantile": quantile,
                        "quantile_method": "linear",
                        "season_half_width": half,
                        "threshold": float(np.quantile(vals, quantile, method="linear")) if ok else np.nan,
                        "status": "ok" if ok else "insufficient_reference",
                    }
                )
    return pd.DataFrame(rows)


def build_threshold_table(observations: pd.DataFrame, origins: list[str], **kwargs) -> pd.DataFrame:
    """One threshold set per forecast origin (each uses only data up to that origin)."""
    return pd.concat(
        [compute_thresholds(observations, origin=o, **kwargs) for o in origins], ignore_index=True
    )


def score_exceedances(
    draw_index: pd.DataFrame, draws: np.ndarray, thresholds: pd.DataFrame
) -> pd.DataFrame:
    """Attach thresholds, observed exceedance and draw-based exceedance probability.

    One output row per draw_index row per method. Rows without a usable threshold keep
    status != 'ok' and have no exceedance or probability.
    """
    if draws.shape[0] != len(draw_index) or not np.array_equal(
        draw_index["row_id"].to_numpy(), np.arange(len(draw_index))
    ):
        raise ValueError("draws rows must align with draw_index row_id 0..n-1.")
    di = draw_index.copy()
    di["target_calendar_month"] = di["target_period"].str[5:7].astype(int)
    keep = [
        "disease", "district", "origin_period", "target_calendar_month", "method",
        "threshold_definition_id", "threshold_label", "reference_start", "reference_end",
        "n_reference_values", "threshold", "status",
    ]
    merged = di.merge(
        thresholds[keep], on=["disease", "district", "origin_period", "target_calendar_month"], how="left"
    )
    merged["status"] = merged["status"].fillna("no_threshold")
    ok = merged["status"].eq("ok")
    merged["observed_exceedance"] = (merged["actual"] > merged["threshold"]).astype("boolean").where(ok)
    prob = np.full(len(merged), np.nan)
    idx = ok.to_numpy()
    rows = merged.loc[idx, "row_id"].to_numpy()
    thr = merged.loc[idx, "threshold"].to_numpy()
    prob[idx] = (draws[rows] > thr[:, None]).mean(axis=1)
    merged["predicted_probability"] = prob
    return merged


def to_probability_records(scored: pd.DataFrame) -> list[OutbreakProbabilityRecord]:
    """Interface records for usable rows; always labelled uncalibrated_exploratory."""
    out = []
    for r in scored[scored["status"] == "ok"].itertuples(index=False):
        out.append(
            OutbreakProbabilityRecord(
                estimator_id=f"draws_{r.model_name}",
                disease=r.disease,
                district=r.district,
                period=r.target_period,
                threshold_definition_id=r.threshold_definition_id,
                threshold=float(r.threshold),
                probability_exceeding_threshold=float(r.predicted_probability),
                calibration_status=CALIBRATION_STATUS,
            )
        )
    return out
