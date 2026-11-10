"""Typed contracts shared by experimental forecasting models."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

import pandas as pd


@dataclass(frozen=True)
class ExperimentSpec:
    experiment_name: str
    experiment_version: str
    disease: str
    classification: str
    geographic_level: str
    forecast_horizon: int
    input_dataset: str
    input_sha256: str
    feature_configuration: dict[str, Any]
    validation_period: str
    task: str = "count_forecasting"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationWindow:
    window_id: str
    phase: str
    origin_period: str
    target_start: str
    target_end: str
    horizon_months: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PredictiveOutput:
    model_name: str
    model_version: str
    disease: str
    classification: str
    district: str
    geographic_level: str
    origin_period: str
    target_period: str
    horizon: int
    actual: float
    predictive_mean: float
    predictive_variance: float | None
    prediction_interval_80_lower: float | None
    prediction_interval_80_upper: float | None
    prediction_interval_95_lower: float | None
    prediction_interval_95_upper: float | None
    predictive_log_score: float | None
    feature_set: str
    validation_phase: str
    readiness_status: str = "evaluated"
    limitations: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelReadiness:
    model_name: str
    model_version: str
    status: str
    reason: str
    task: str
    requirements: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ForecastModel(Protocol):
    name: str
    version: str

    def fit(self, training: pd.DataFrame, *, climate: bool = False) -> "ForecastModel":
        ...

    def forecast(
        self,
        training: pd.DataFrame,
        horizon: int,
        *,
        climate: bool = False,
        actuals: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        ...
