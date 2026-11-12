"""Retrospective unusual-activity detectors (EWMA and CUSUM) on monthly counts.

Exploratory and non-operational: there are no independently reviewed outbreak
labels or official thresholds, so these flags are statistical deviations from a
seasonal baseline, not validated outbreak alerts. Parameters are conventional
textbook defaults and were not tuned.

Method, per (disease, district) series:
  1. Square-root transform of counts to stabilise variance.
  2. Baseline for a month = median of the same calendar month in STRICTLY EARLIER
     years (expanding window; no future data).
  3. Scale = robust (MAD-based) spread of residuals available BEFORE that month,
     with a floor, so low-count districts do not get a near-zero scale.
  4. z = residual / scale; EWMA and one-sided (upper) CUSUM run on z.
Scoring starts after the end of the baseline period.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from caregrid.model_intelligence.interfaces import AnomalyRecord

REQUIRED_COLUMNS = ("disease", "district", "period", "cases")


def load_confirmed_observations(path: str | Path) -> pd.DataFrame:
    """Load Confirmed district-month counts; unavailable rows are dropped, never zero-filled."""
    df = pd.read_csv(path)
    keep = (df["classification"] == "Confirmed") & (df["cases_available"].astype(str) == "True")
    out = df.loc[keep, list(REQUIRED_COLUMNS)].copy()
    if out["cases"].isna().any():
        raise ValueError("Confirmed rows marked available contain missing case counts.")
    out["cases"] = out["cases"].astype(int)
    return out.sort_values(["disease", "district", "period"]).reset_index(drop=True)


def _check_series(periods: list[str], label: str) -> None:
    idx = [int(p[:4]) * 12 + int(p[5:7]) for p in periods]
    if any(b - a != 1 for a, b in zip(idx, idx[1:])):
        raise ValueError(f"Series {label} has missing or duplicate months; periods must be consecutive.")


def _robust_scale(residuals: list[float], floor: float) -> float:
    arr = np.asarray(residuals, dtype=float)
    mad = float(np.median(np.abs(arr - np.median(arr))))
    return max(floor, 1.4826 * mad)


def _score_series(
    periods: list[str],
    counts: list[int],
    baseline_end: str,
    *,
    min_prior_years: int,
    lam: float,
    ewma_width: float,
    cusum_k: float,
    cusum_h: float,
    scale_floor: float,
) -> list[dict]:
    months = [int(p[5:7]) for p in periods]
    y = np.sqrt(np.asarray(counts, dtype=float))
    in_base = [i for i, p in enumerate(periods) if p <= baseline_end]
    if not in_base:
        raise ValueError("No observations fall inside the baseline period.")

    # In-sample residuals inside the designated baseline window only.
    history: list[float] = []
    for i in in_base:
        same = [y[j] for j in in_base if months[j] == months[i]]
        if len(same) < min_prior_years:
            raise ValueError(
                f"Baseline period needs at least {min_prior_years} years of data per calendar month."
            )
        history.append(float(y[i] - np.median(same)))

    rows: list[dict] = []
    ewma = 0.0
    cusum = 0.0
    n = 0
    for i in range(in_base[-1] + 1, len(periods)):
        prior = [y[j] for j in range(i) if months[j] == months[i]]
        if len(prior) < min_prior_years:
            continue
        baseline = float(np.median(prior))
        residual = float(y[i] - baseline)
        scale = _robust_scale(history, scale_floor)  # uses only residuals before i
        z = residual / scale
        history.append(residual)

        n += 1
        ewma = lam * z + (1.0 - lam) * ewma
        limit = ewma_width * math.sqrt(lam / (2.0 - lam) * (1.0 - (1.0 - lam) ** (2 * n)))
        cusum_pre_reset = max(0.0, cusum + z - cusum_k)
        cusum_flag = cusum_pre_reset > cusum_h
        cusum = 0.0 if cusum_flag else cusum_pre_reset

        rows.append(
            {
                "period": periods[i],
                "observed": int(counts[i]),
                "baseline": baseline**2,
                "ewma_score": ewma / limit,
                "ewma_flag": ewma > limit,
                "cusum_score": cusum_pre_reset / cusum_h,
                "cusum_flag": cusum_flag,
            }
        )
    return rows


class _BaseDetector:
    detector_id: str = ""
    _prefix: str = ""

    def __init__(
        self,
        *,
        min_prior_years: int = 3,
        lam: float = 0.3,
        ewma_width: float = 3.0,
        cusum_k: float = 0.5,
        cusum_h: float = 4.0,
        scale_floor: float = 0.5,
    ) -> None:
        self._params = dict(
            min_prior_years=min_prior_years,
            lam=lam,
            ewma_width=ewma_width,
            cusum_k=cusum_k,
            cusum_h=cusum_h,
            scale_floor=scale_floor,
        )

    def detect(
        self, observations: pd.DataFrame, *, baseline_period: tuple[str, str]
    ) -> list[AnomalyRecord]:
        missing = [c for c in REQUIRED_COLUMNS if c not in observations.columns]
        if missing:
            raise ValueError(f"observations is missing columns: {missing}")
        records: list[AnomalyRecord] = []
        for (disease, district), grp in observations.groupby(["disease", "district"], sort=True):
            grp = grp.sort_values("period")
            periods = grp["period"].tolist()
            _check_series(periods, f"{disease}/{district}")
            rows = _score_series(
                periods, grp["cases"].astype(int).tolist(), baseline_period[1], **self._params
            )
            for r in rows:
                records.append(
                    AnomalyRecord(
                        detector_id=self.detector_id,
                        disease=disease,
                        district=district,
                        period=r["period"],
                        observed_count=r["observed"],
                        baseline=r["baseline"],
                        anomaly_score=float(r[f"{self._prefix}_score"]),
                        unusual_activity_flag=bool(r[f"{self._prefix}_flag"]),
                    )
                )
        return records


class EwmaDetector(_BaseDetector):
    """EWMA on standardised sqrt-scale residuals; score = statistic / control limit."""

    detector_id = "ewma_sqrt_seasonal_median_v1"
    _prefix = "ewma"


class CusumDetector(_BaseDetector):
    """One-sided upper CUSUM (reset after a signal); score = statistic / decision interval."""

    detector_id = "cusum_sqrt_seasonal_median_v1"
    _prefix = "cusum"
