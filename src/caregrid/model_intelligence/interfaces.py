"""Separate extension contracts for forecasting and outbreak-intelligence tasks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd


@dataclass(frozen=True)
class ForecastDistribution:
    family: str
    mean: float
    variance: float | None
    lower_80: float | None
    upper_80: float | None
    lower_95: float | None
    upper_95: float | None
    log_score: float | None


@dataclass(frozen=True)
class ForecastRecord:
    model_id: str
    disease: str
    district: str
    origin_period: str
    target_period: str
    horizon: int
    point_prediction: float
    distribution: ForecastDistribution | None


@dataclass(frozen=True)
class AnomalyRecord:
    detector_id: str
    disease: str
    district: str
    period: str
    observed_count: int
    baseline: float | None
    anomaly_score: float
    unusual_activity_flag: bool


@dataclass(frozen=True)
class OutbreakProbabilityRecord:
    estimator_id: str
    disease: str
    district: str
    period: str
    threshold_definition_id: str
    threshold: float
    probability_exceeding_threshold: float
    calibration_status: str


class ForecastingModel(Protocol):
    """Predict future counts; evaluation is forecast-error and interval based."""

    model_id: str

    def fit(self, observations: pd.DataFrame, features: pd.DataFrame) -> None:
        ...

    def predict(
        self,
        origin: str,
        horizon: int,
        features_available_at_origin: pd.DataFrame,
    ) -> list[ForecastRecord]:
        ...


class UnusualActivityDetector(Protocol):
    """Identify retrospective deviations from an expected activity baseline."""

    detector_id: str

    def detect(
        self,
        observations: pd.DataFrame,
        *,
        baseline_period: tuple[str, str],
    ) -> list[AnomalyRecord]:
        ...


class OutbreakProbabilityEstimator(Protocol):
    """Estimate threshold exceedance only with a defined threshold and labels."""

    estimator_id: str

    def fit(
        self,
        observations: pd.DataFrame,
        *,
        threshold_definition_id: str,
        outbreak_labels: pd.DataFrame,
    ) -> None:
        ...

    def probability(
        self,
        inputs: pd.DataFrame,
        *,
        threshold_definition_id: str,
    ) -> list[OutbreakProbabilityRecord]:
        ...


@dataclass(frozen=True)
class TaskMetricContract:
    task: str
    primary_metrics: tuple[str, ...]
    required_reference_data: tuple[str, ...]


TASK_METRIC_CONTRACTS: dict[str, TaskMetricContract] = {
    "count_forecasting": TaskMetricContract(
        task="count_forecasting",
        primary_metrics=("MAE", "RMSE", "count log score", "interval coverage", "interval score"),
        required_reference_data=("chronological forecast origins", "held-out observed counts"),
    ),
    "retrospective_unusual_activity_detection": TaskMetricContract(
        task="retrospective_unusual_activity_detection",
        primary_metrics=("sensitivity", "specificity", "precision-recall", "false alerts per district-year"),
        required_reference_data=("independently reviewed unusual-activity labels",),
    ),
    "probabilistic_outbreak_threshold_exceedance": TaskMetricContract(
        task="probabilistic_outbreak_threshold_exceedance",
        primary_metrics=("Brier score", "log loss", "reliability", "calibration slope"),
        required_reference_data=("defined epidemiological threshold", "verified outbreak labels"),
    ),
}
