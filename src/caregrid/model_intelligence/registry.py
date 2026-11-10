"""Declarative registry for implemented and planned analytical models."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SUPPORTED_DISEASES = ("Dengue", "Leptospirosis")
HISTORY_FEATURES = (
    "district",
    "month_of_year",
    "linear_trend",
    "previous_month_confirmed_cases",
)
CLIMATE_FEATURES = (
    *HISTORY_FEATURES,
    "previous_month_rainfall",
    "preceding_3_month_rainfall_sum",
    "previous_month_mean_temperature",
    "previous_month_temperature_range",
    "previous_month_relative_humidity",
    "previous_month_dew_point",
)


@dataclass(frozen=True)
class ModelRegistration:
    model_id: str
    model_name: str
    version: str | None
    analytical_task: str
    supported_diseases: tuple[str, ...]
    required_features: tuple[str, ...]
    training_requirements: tuple[str, ...]
    minimum_horizon: int
    maximum_horizon: int
    prediction_output: str
    predictive_uncertainty: str
    readiness_status: str
    failure_status: str
    limitations: tuple[str, ...] = ()
    extensions: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for key in ("supported_diseases", "required_features", "training_requirements", "limitations"):
            value[key] = list(value[key])
        return value

    def supports(self, disease: str, horizon: int) -> bool:
        return (
            disease in self.supported_diseases
            and self.minimum_horizon <= horizon <= self.maximum_horizon
        )


def build_default_registry() -> dict[str, ModelRegistration]:
    """Create registrations without importing or instantiating model runtimes."""
    registrations = [
        ModelRegistration(
            model_id="seasonal_naive::disease_history",
            model_name="seasonal_naive",
            version="1.0",
            analytical_task="count_forecasting",
            supported_diseases=SUPPORTED_DISEASES,
            required_features=("district", "same_month_previous_year_cases"),
            training_requirements=(
                "At least 24 consecutive monthly observations per district",
                "Same source-native classification throughout training",
            ),
            minimum_horizon=1,
            maximum_horizon=12,
            prediction_output="PredictiveOutput; mean and empirical residual intervals",
            predictive_uncertainty="empirical_prediction_intervals; log score unavailable",
            readiness_status="evaluated_exploratory",
            failure_status="none_in_saved_experiment",
            limitations=("Empirical pooled residual intervals are not distributionally calibrated.",),
        ),
        ModelRegistration(
            model_id="poisson_regression::disease_history",
            model_name="poisson_regression",
            version="1.0",
            analytical_task="count_forecasting",
            supported_diseases=SUPPORTED_DISEASES,
            required_features=HISTORY_FEATURES,
            training_requirements=(
                "Non-negative integer count response",
                "Training-only lag features",
                "Sufficient observations for district and monthly effects",
            ),
            minimum_horizon=1,
            maximum_horizon=12,
            prediction_output="PredictiveOutput; Poisson predictive distribution",
            predictive_uncertainty="Poisson_distributional_prediction_intervals",
            readiness_status="evaluated_exploratory",
            failure_status="none_in_saved_experiment",
            limitations=("Poisson equidispersion may be inadequate for overdispersed counts.",),
        ),
        ModelRegistration(
            model_id="negative_binomial_regression::disease_history",
            model_name="negative_binomial_regression",
            version="1.0",
            analytical_task="count_forecasting",
            supported_diseases=SUPPORTED_DISEASES,
            required_features=HISTORY_FEATURES,
            training_requirements=(
                "Non-negative integer count response",
                "Training-only lag features",
                "More complete training rows than design-matrix parameters",
            ),
            minimum_horizon=1,
            maximum_horizon=12,
            prediction_output="PredictiveOutput; NB2 predictive distribution",
            predictive_uncertainty="negative_binomial_distributional_prediction_intervals",
            readiness_status="evaluated_exploratory",
            failure_status="none_in_saved_experiment",
            limitations=("Regularized pooled fixed effects; not a hierarchical Bayesian model.",),
        ),
        ModelRegistration(
            model_id="poisson_regression::disease_history_and_climate",
            model_name="poisson_regression",
            version="1.0",
            analytical_task="count_forecasting",
            supported_diseases=SUPPORTED_DISEASES,
            required_features=CLIMATE_FEATURES,
            training_requirements=(
                "All history-only Poisson requirements",
                "Complete representative-location weather for all training rows",
                "Weather features available at forecast origin",
            ),
            minimum_horizon=1,
            maximum_horizon=12,
            prediction_output="PredictiveOutput; Poisson predictive distribution",
            predictive_uncertainty="Poisson_distributional_prediction_intervals",
            readiness_status="evaluated_exploratory",
            failure_status="none_in_saved_experiment",
            limitations=("Weather is from one representative location per district.",),
        ),
        ModelRegistration(
            model_id="negative_binomial_regression::disease_history_and_climate",
            model_name="negative_binomial_regression",
            version="1.0",
            analytical_task="count_forecasting",
            supported_diseases=SUPPORTED_DISEASES,
            required_features=CLIMATE_FEATURES,
            training_requirements=(
                "All history-only NB2 requirements",
                "Complete representative-location weather for all training rows",
                "Weather features available at forecast origin",
            ),
            minimum_horizon=1,
            maximum_horizon=12,
            prediction_output="PredictiveOutput; NB2 predictive distribution",
            predictive_uncertainty="negative_binomial_distributional_prediction_intervals",
            readiness_status="evaluated_exploratory",
            failure_status="none_in_saved_experiment",
            limitations=(
                "Regularized pooled fixed effects; not a hierarchical Bayesian model.",
                "Weather is from one representative location per district.",
            ),
        ),
    ]
    planned = (
        ("bayesian_poisson", "count_forecasting"),
        ("gaussian_process", "count_forecasting"),
        ("student_t_process", "count_forecasting"),
        ("bayesian_structural_time_series", "count_forecasting"),
        ("hidden_markov_model", "retrospective_unusual_activity_detection"),
        ("ensemble_forecast", "count_forecasting"),
    )
    for model_name, task in planned:
        registrations.append(
            ModelRegistration(
                model_id=f"{model_name}::planned",
                model_name=model_name,
                version=None,
                analytical_task=task,
                supported_diseases=SUPPORTED_DISEASES,
                required_features=(),
                training_requirements=("Task-specific input and evidence requirements not yet evaluated.",),
                minimum_horizon=1,
                maximum_horizon=12,
                prediction_output="Task-specific output contract; algorithm not implemented",
                predictive_uncertainty="not_available",
                readiness_status="planned_not_implemented",
                failure_status="not_run",
                limitations=("Registered as an extension point only; no predictions or evaluation exist.",),
            )
        )
    registrations.append(
        ModelRegistration(
            model_id="bayesian_negative_binomial::planned",
            model_name="bayesian_negative_binomial",
            version=None,
            analytical_task="count_forecasting",
            supported_diseases=SUPPORTED_DISEASES,
            required_features=(),
            training_requirements=(
                "Regularizing priors and multiple chains",
                "R-hat, effective-sample-size, divergence, and predictive checks",
            ),
            minimum_horizon=1,
            maximum_horizon=12,
            prediction_output="Posterior predictive count distribution",
            predictive_uncertainty="not_available",
            readiness_status="unavailable_inference_dependency",
            failure_status="not_run; PyMC/Stan runtime not installed",
            limitations=(
                "The saved experiment contains no Bayesian NB posterior samples or predictions.",
                "Requires a separate posterior diagnostic pilot before model evaluation.",
            ),
        )
    )
    registrations.append(
        ModelRegistration(
            model_id="outbreak_probability::planned",
            model_name="outbreak_probability",
            version=None,
            analytical_task="probabilistic_outbreak_threshold_exceedance",
            supported_diseases=SUPPORTED_DISEASES,
            required_features=(),
            training_requirements=(
                "Independently defined epidemiological threshold",
                "Verified event labels and evaluation windows",
                "Prospective availability of all predictors",
            ),
            minimum_horizon=0,
            maximum_horizon=12,
            prediction_output="Calibrated probability of exceeding a defined threshold",
            predictive_uncertainty="not_available",
            readiness_status="blocked_missing_thresholds_and_event_labels",
            failure_status="not_run",
            limitations=("No operational outbreak alerts are supported.",),
        )
    )
    return {entry.model_id: entry for entry in registrations}
