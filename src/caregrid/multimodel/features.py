"""Leakage-aware shared design matrices and climate feature preparation."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

from caregrid.multimodel.data import WEATHER_FEATURES, ModelDataError

BASE_NUMERIC = ("trend_years", "log_lag_cases")
CLIMATE_NUMERIC = (
    "log1p_lag1_rainfall",
    "log1p_lag3_rainfall",
    "lag1_temperature_mean",
    "lag1_temperature_range",
    "lag1_relative_humidity",
    "lag1_dew_point",
)


@dataclass
class FeatureEncoder:
    district_levels: tuple[str, ...]
    numeric_columns: tuple[str, ...]
    month_levels: tuple[int, ...] = tuple(range(1, 13))
    center: np.ndarray | None = None
    scale: np.ndarray | None = None
    columns: tuple[str, ...] = ()

    def _raw(self, frame: pd.DataFrame) -> tuple[np.ndarray, tuple[str, ...]]:
        numeric = frame.loc[:, self.numeric_columns].to_numpy(dtype=float)
        districts = pd.get_dummies(
            pd.Categorical(frame["district"], categories=self.district_levels),
            dtype=float,
        ).to_numpy()
        months = pd.get_dummies(
            pd.Categorical(frame["month_num"], categories=self.month_levels),
            dtype=float,
        ).to_numpy()
        names = (
            *self.numeric_columns,
            *(f"district[{name}]" for name in self.district_levels),
            *(f"month[{name:02d}]" for name in self.month_levels),
        )
        matrix = np.column_stack((numeric, districts, months))
        if not np.isfinite(matrix).all():
            raise ModelDataError("Feature matrix contains missing or non-finite values.")
        return matrix, tuple(names)

    def fit_transform(self, frame: pd.DataFrame) -> np.ndarray:
        matrix, names = self._raw(frame)
        numeric_count = len(self.numeric_columns)
        self.center = np.zeros(matrix.shape[1], dtype=float)
        self.scale = np.ones(matrix.shape[1], dtype=float)
        self.center[:numeric_count] = matrix[:, :numeric_count].mean(axis=0)
        scales = matrix[:, :numeric_count].std(axis=0)
        self.scale[:numeric_count] = np.where(scales > 0, scales, 1.0)
        self.columns = names
        return (matrix - self.center) / self.scale

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        if self.center is None or self.scale is None:
            raise ModelDataError("Feature encoder must be fit before transforming.")
        matrix, names = self._raw(frame)
        if names != self.columns:
            raise ModelDataError("Prediction feature columns differ from training.")
        return (matrix - self.center) / self.scale


def add_climate_training_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["log1p_lag1_rainfall"] = np.log1p(
        result["lag1_precipitation_sum_mm"]
    )
    result["log1p_lag3_rainfall"] = np.log1p(result["lag3_rainfall_sum_mm"])
    result["lag1_temperature_mean"] = result["lag1_temperature_2m_mean_c"]
    result["lag1_temperature_range"] = result["lag1_temperature_range_c"]
    result["lag1_relative_humidity"] = (
        result["lag1_relative_humidity_2m_mean_pct"] / 100
    )
    result["lag1_dew_point"] = result["lag1_dew_point_2m_mean_c"]
    return result


def prepare_training_rows(
    training: pd.DataFrame,
    *,
    climate: bool,
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    data = training.dropna(subset=["lag_cases"]).copy()
    numeric = list(BASE_NUMERIC)
    if climate:
        data = add_climate_training_features(data)
        numeric.extend(CLIMATE_NUMERIC)
    data = data.dropna(subset=numeric)
    if data.empty:
        raise ModelDataError("No complete training rows remain after lag features.")
    return data, tuple(numeric)


def recursive_prediction_rows(
    training: pd.DataFrame,
    target_period: str,
    *,
    climate: bool,
    origin_climate: dict[str, float] | None = None,
) -> pd.DataFrame:
    last_rows = training.sort_values("period_start").groupby(
        "district", sort=False
    ).tail(1).set_index("district")
    period = pd.Period(target_period, freq="M")
    trend = period.year + (period.month - 1) / 12 - 2016
    rows = []
    for district, last in last_rows.iterrows():
        previous = float(last["cases"])
        row = {
            "district": district,
            "period": target_period,
            "period_start": period.to_timestamp(),
            "month_num": period.month,
            "trend_years": trend,
            "lag_cases": previous,
            "log_lag_cases": float(np.log1p(previous)),
        }
        if climate:
            if origin_climate is None or district not in origin_climate:
                raise ModelDataError("Climate forecast requires origin-only weather.")
            climate_values = origin_climate[district]
            row.update(climate_values)
            row["log1p_lag1_rainfall"] = np.log1p(
                climate_values["lag1_precipitation_sum_mm"]
            )
            row["log1p_lag3_rainfall"] = np.log1p(
                climate_values["lag3_rainfall_sum_mm"]
            )
            row["lag1_temperature_mean"] = climate_values[
                "lag1_temperature_2m_mean_c"
            ]
            row["lag1_temperature_range"] = climate_values[
                "lag1_temperature_range_c"
            ]
            row["lag1_relative_humidity"] = (
                climate_values["lag1_relative_humidity_2m_mean_pct"] / 100
            )
            row["lag1_dew_point"] = climate_values["lag1_dew_point_2m_mean_c"]
        rows.append(row)
    return pd.DataFrame(rows)


def latest_origin_climate(training: pd.DataFrame) -> dict[str, float]:
    """Freeze climate features at the origin; never access target-period weather."""
    data = training.sort_values("period_start")
    origins = []
    for district, group in data.groupby("district", sort=False):
        group = group.sort_values("period_start")
        if len(group) < 3:
            raise ModelDataError(f"Insufficient weather history for district {district}.")
        last_three = group.tail(3)
        origins.append({
            "district": district,
            "lag1_precipitation_sum_mm": float(last_three.iloc[-1]["precipitation_sum_mm"]),
            "lag3_rainfall_sum_mm": float(last_three["precipitation_sum_mm"].sum()),
            "lag1_temperature_2m_mean_c": float(last_three.iloc[-1]["temperature_2m_mean_c"]),
            "lag1_temperature_range_c": float(
                last_three.iloc[-1]["temperature_2m_max_c"]
                - last_three.iloc[-1]["temperature_2m_min_c"]
            ),
            "lag1_relative_humidity_2m_mean_pct": float(
                last_three.iloc[-1]["relative_humidity_2m_mean_pct"]
            ),
            "lag1_dew_point_2m_mean_c": float(last_three.iloc[-1]["dew_point_2m_mean_c"]),
        })
    return {
        row["district"]: {key: value for key, value in row.items() if key != "district"}
        for row in origins
    }
