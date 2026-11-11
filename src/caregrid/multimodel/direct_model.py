"""Direct (non-recursive) negative binomial forecasting model.

For horizon h, one model is fit on pairs (target month t, actual cases at t-h).
At forecast time the lag is the actual case count at the origin month, so no
predictions are fed back. Missing lags drop the row; they are never set to 0.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from caregrid.multimodel.models import (
    CountModelError,
    NegativeBinomialCountModel,
    _distribution_summary,
)


def build_direct_training(training: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Pair each month with the actual cases exactly `horizon` months earlier."""
    data = training.dropna(subset=["cases"]).copy()
    data = data.drop(columns=["lag_cases", "log_lag_cases"], errors="ignore")
    lookup = data[["district", "period", "cases"]].rename(
        columns={"period": "lag_period", "cases": "lag_value"}
    )
    if lookup.duplicated(["district", "lag_period"]).any():
        raise CountModelError("Training data has duplicate district-month keys.")
    data["lag_period"] = [
        str(period - horizon) for period in pd.PeriodIndex(data["period"], freq="M")
    ]
    merged = data.merge(lookup, on=["district", "lag_period"], how="left")
    merged["lag_cases"] = merged["lag_value"]
    merged["log_lag_cases"] = np.log1p(merged["lag_value"])
    merged = merged.dropna(subset=["lag_cases"])
    return merged.drop(columns=["lag_value", "lag_period"]).reset_index(drop=True)


class DirectNegativeBinomialModel:
    name = "direct_negative_binomial"
    version = "1.0"

    def __init__(self, ridge_alpha: float = 0.1, max_horizon: int = 12) -> None:
        self.ridge_alpha = ridge_alpha
        self.max_horizon = max_horizon
        self.models: dict[int, NegativeBinomialCountModel] = {}
        self.district_levels: tuple[str, ...] = ()
        self.n_training_rows = 0
        self.climate = False

    def fit(self, training: pd.DataFrame, *, climate: bool = False) -> "DirectNegativeBinomialModel":
        if climate:
            raise CountModelError("Direct model is history-only for now.")
        self.district_levels = tuple(sorted(training["district"].unique()))
        self.models = {}
        total = 0
        for step in range(1, self.max_horizon + 1):
            table = build_direct_training(training, step)
            model = NegativeBinomialCountModel(ridge_alpha=self.ridge_alpha)
            model.fit(table, climate=False)
            self.models[step] = model
            total += model.n_training_rows
        self.n_training_rows = total
        return self

    def forecast(
        self,
        training: pd.DataFrame,
        horizon: int,
        *,
        climate: bool = False,
        actuals: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        if not self.models:
            raise CountModelError("Model must be fit before forecasting.")
        if climate:
            raise CountModelError("Direct model is history-only for now.")
        if horizon < 1 or horizon > self.max_horizon:
            raise CountModelError("Forecast horizon is outside the fitted range.")
        if actuals.duplicated(["district", "period"]).any():
            raise CountModelError("Validation actuals contain duplicate district-month keys.")
        origin = str(training["period"].max())
        origin_rows = training[training["period"].eq(origin)]
        if origin_rows["district"].duplicated().any():
            raise CountModelError("Duplicate origin rows.")
        if origin_rows["cases"].isna().any():
            raise CountModelError("Origin month has missing cases; refusing to treat as zero.")
        origin_cases = origin_rows.set_index("district")["cases"].to_dict()
        if set(origin_cases) != set(self.district_levels):
            raise CountModelError("Forecast districts differ from the fitted districts.")
        output: list[dict[str, Any]] = []
        for step in range(1, horizon + 1):
            period = pd.Period(origin, freq="M") + step
            period_string = str(period)
            rows = []
            for district in self.district_levels:
                previous = float(origin_cases[district])
                rows.append({
                    "district": district,
                    "period": period_string,
                    "month_num": period.month,
                    "trend_years": period.year + (period.month - 1) / 12 - 2016,
                    "lag_cases": previous,
                    "log_lag_cases": float(np.log1p(previous)),
                })
            future = pd.DataFrame(rows)
            model = self.models[step]
            matrix = model.encoder.transform(future)
            distribution = model._distribution(matrix)
            means = np.asarray(distribution.mean(), dtype=float).reshape(-1)
            lookup = (
                actuals.loc[actuals["period"].eq(period_string), ["district", "cases"]]
                .set_index("district")["cases"].to_dict()
            )
            for index, row in future.iterrows():
                district = row["district"]
                if district not in lookup:
                    raise CountModelError(
                        f"Validation actual is missing for {district}/{period_string}."
                    )
                actual = int(lookup[district])
                summary = _distribution_summary(distribution, index)
                output.append({
                    "district": district,
                    "period": period_string,
                    "horizon": step,
                    "actual": actual,
                    "predictive_mean": float(means[index]),
                    "predictive_variance": summary["variance"],
                    "prediction_interval_80_lower": summary["lower_80"],
                    "prediction_interval_80_upper": summary["upper_80"],
                    "prediction_interval_95_lower": summary["lower_95"],
                    "prediction_interval_95_upper": summary["upper_95"],
                    "predictive_log_score": float(distribution.logpmf(actual)[index]),
                    "predictive_distribution": "NegativeBinomial",
                })
        return output
