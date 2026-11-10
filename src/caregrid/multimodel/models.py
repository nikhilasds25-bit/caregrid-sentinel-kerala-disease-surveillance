"""Count-forecast models with common recursive prediction contracts."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln, xlogy
from scipy.stats import nbinom, poisson
from sklearn.linear_model import PoissonRegressor

from caregrid.multimodel.data import ModelDataError
from caregrid.multimodel.features import (
    FeatureEncoder,
    latest_origin_climate,
    prepare_training_rows,
    recursive_prediction_rows,
)


class CountModelError(ValueError):
    """Raised when a count model cannot be fit or forecast reliably."""


def _distribution_summary(distribution: Any, index: int) -> dict[str, float | None]:
    return {
        "variance": float(np.asarray(distribution.var())[index]),
        "lower_80": float(np.asarray(distribution.ppf(0.10))[index]),
        "upper_80": float(np.asarray(distribution.ppf(0.90))[index]),
        "lower_95": float(np.asarray(distribution.ppf(0.025))[index]),
        "upper_95": float(np.asarray(distribution.ppf(0.975))[index]),
    }


class RecursiveCountModel(ABC):
    name = "abstract_count_model"
    version = "1.0"

    def __init__(self) -> None:
        self.climate = False
        self.encoder: FeatureEncoder | None = None
        self.numeric_columns: tuple[str, ...] = ()
        self.district_levels: tuple[str, ...] = ()
        self.dispersion_alpha: float | None = None
        self.n_training_rows = 0

    def fit(self, training: pd.DataFrame, *, climate: bool = False) -> "RecursiveCountModel":
        self.climate = climate
        complete, numeric_columns = prepare_training_rows(training, climate=climate)
        self.n_training_rows = len(complete)
        self.numeric_columns = numeric_columns
        self.district_levels = tuple(sorted(training["district"].unique()))
        self.encoder = FeatureEncoder(self.district_levels, numeric_columns)
        matrix = self.encoder.fit_transform(complete)
        self._fit_distribution(matrix, complete["cases"].to_numpy(dtype=float))
        return self

    @abstractmethod
    def _fit_distribution(self, matrix: np.ndarray, counts: np.ndarray) -> None:
        ...

    @abstractmethod
    def _distribution(self, matrix: np.ndarray) -> Any:
        ...

    @abstractmethod
    def _distribution_name(self) -> str:
        ...

    def forecast(
        self,
        training: pd.DataFrame,
        horizon: int,
        *,
        climate: bool = False,
        actuals: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        if self.encoder is None:
            raise CountModelError("Model must be fit before forecasting.")
        if climate != self.climate:
            raise CountModelError("Forecast feature configuration differs from fit.")
        if horizon < 1:
            raise CountModelError("Forecast horizon must be at least one month.")
        if actuals.duplicated(["district", "period"]).any():
            raise CountModelError("Validation actuals contain duplicate district-month keys.")
        origin_climate = latest_origin_climate(training) if climate else None
        origin = training["period"].max()
        targets = pd.period_range(pd.Period(origin, freq="M") + 1, periods=horizon, freq="M")
        history = training.copy()
        output: list[dict[str, Any]] = []
        for step, period in enumerate(targets, start=1):
            period_string = str(period)
            future = recursive_prediction_rows(
                history,
                period_string,
                climate=climate,
                origin_climate=origin_climate,
            )
            if set(future["district"]) != set(self.district_levels):
                raise CountModelError("Forecast districts differ from the fitted districts.")
            matrix = self.encoder.transform(future)
            distribution = self._distribution(matrix)
            means = np.asarray(distribution.mean(), dtype=float).reshape(-1)
            actual_rows = actuals.loc[
                actuals["period"].eq(period_string),
                ["district", "cases"],
            ]
            actual_lookup = actual_rows.set_index("district")["cases"].to_dict()
            for index, row in future.iterrows():
                district = row["district"]
                if district not in actual_lookup:
                    raise CountModelError(
                        f"Validation actual is missing for {district}/{period_string}."
                    )
                actual = int(actual_lookup[district])
                log_score = float(distribution.logpmf(actual)[index])
                summary = _distribution_summary(distribution, index)
                record = {
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
                    "predictive_log_score": log_score,
                    "predictive_distribution": self._distribution_name(),
                }
                output.append(record)
                history = pd.concat(
                    [
                        history,
                        pd.DataFrame([{
                            "district": district,
                            "period": period_string,
                            "period_start": period.to_timestamp(),
                            "month_num": period.month,
                            "trend_years": (
                                period.year + (period.month - 1) / 12 - 2016
                            ),
                            "cases": float(means[index]),
                            "lag_cases": np.nan,
                            "log_lag_cases": np.nan,
                            **(
                                origin_climate[district]
                                if origin_climate is not None else {}
                            ),
                        }]),
                    ],
                    ignore_index=True,
                )
            # Future predictions use only origin-known weather and recursively forecast
            # disease lags; actual target-period values are never appended.
        return output


class PoissonCountModel(RecursiveCountModel):
    name = "poisson_regression"

    def __init__(self, alpha: float = 0.1) -> None:
        super().__init__()
        self.alpha = alpha
        self.estimator: PoissonRegressor | None = None

    def _fit_distribution(self, matrix: np.ndarray, counts: np.ndarray) -> None:
        self.estimator = PoissonRegressor(
            alpha=self.alpha,
            fit_intercept=False,
            max_iter=500,
            tol=1e-8,
        )
        self.estimator.fit(matrix, counts)

    def _distribution(self, matrix: np.ndarray) -> Any:
        if self.estimator is None:
            raise CountModelError("Poisson regression has not been fit.")
        means = np.clip(self.estimator.predict(matrix), 1e-9, 1e9)
        return poisson(mu=means)

    def _distribution_name(self) -> str:
        return "Poisson"


class NegativeBinomialCountModel(RecursiveCountModel):
    name = "negative_binomial_regression"

    def __init__(self, ridge_alpha: float = 0.1) -> None:
        super().__init__()
        self.ridge_alpha = ridge_alpha
        self.coefficients: np.ndarray | None = None

    def _fit_distribution(self, matrix: np.ndarray, counts: np.ndarray) -> None:
        if len(counts) <= matrix.shape[1]:
            raise CountModelError(
                "Negative Binomial fit requires more observations than predictors."
            )
        initial = np.zeros(matrix.shape[1] + 1, dtype=float)
        initial[-1] = np.log(0.2)

        def objective(parameters: np.ndarray) -> float:
            coefficients = parameters[:-1]
            alpha = float(np.exp(parameters[-1]))
            eta = np.clip(matrix @ coefficients, -15, 15)
            mean = np.exp(eta)
            size = 1.0 / alpha
            probability = size / (size + mean)
            log_likelihood = (
                gammaln(counts + size)
                - gammaln(size)
                - gammaln(counts + 1)
                + size * np.log(probability)
                + xlogy(counts, 1 - probability)
            ).sum()
            penalty = 0.5 * self.ridge_alpha * float(coefficients @ coefficients)
            return float(-log_likelihood + penalty)

        result = minimize(
            objective,
            initial,
            method="L-BFGS-B",
            bounds=[(None, None)] * matrix.shape[1] + [(-6.0, 2.0)],
            options={"maxiter": 4000, "ftol": 1e-10},
        )
        if not result.success:
            raise CountModelError(
                f"Negative Binomial optimization failed: {result.message}"
            )
        if not np.isfinite(result.x).all():
            raise CountModelError("Negative Binomial optimization returned non-finite parameters.")
        self.coefficients = result.x[:-1]
        self.dispersion_alpha = float(np.exp(result.x[-1]))

    def _distribution(self, matrix: np.ndarray) -> Any:
        if self.coefficients is None or self.dispersion_alpha is None:
            raise CountModelError("Negative Binomial regression has not been fit.")
        mean = np.exp(np.clip(matrix @ self.coefficients, -15, 15))
        size = 1 / self.dispersion_alpha
        probability = size / (size + mean)
        return nbinom(n=size, p=probability)

    def _distribution_name(self) -> str:
        return "NegativeBinomial"


class SeasonalNaiveModel:
    """Previous-year same-month benchmark with training-only residual intervals."""

    name = "seasonal_naive"
    version = "1.0"

    def __init__(self, residual_years: int = 3) -> None:
        self.residual_years = residual_years
        self.residuals: np.ndarray = np.asarray([], dtype=float)
        self.n_training_rows = 0

    def fit(
        self,
        training: pd.DataFrame,
        *,
        climate: bool = False,
    ) -> "SeasonalNaiveModel":
        if climate:
            raise CountModelError("Seasonal Naive does not use climate predictors.")
        self.n_training_rows = len(training)
        residuals = []
        data = training.sort_values(["district", "period_start"])
        latest_period = pd.Period(training["period"].max(), freq="M")
        for _, group in data.groupby("district", sort=False):
            indexed = group.set_index("period")
            for period_string, row in indexed.iterrows():
                previous_year = str(pd.Period(period_string, freq="M") - 12)
                if previous_year in indexed.index:
                    case_period = pd.Period(period_string, freq="M")
                    age_months = (
                        (latest_period.year - case_period.year) * 12
                        + latest_period.month - case_period.month
                    )
                    if age_months < 12 * self.residual_years:
                        residuals.append(
                            float(row["cases"] - indexed.loc[previous_year, "cases"])
                        )
        self.residuals = np.asarray(residuals, dtype=float)
        if len(self.residuals) < 12:
            raise CountModelError(
                "Seasonal Naive intervals require at least 12 training residuals."
            )
        return self

    def forecast(
        self,
        training: pd.DataFrame,
        horizon: int,
        *,
        climate: bool = False,
        actuals: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        if climate:
            raise CountModelError("Seasonal Naive does not use climate predictors.")
        if actuals.duplicated(["district", "period"]).any():
            raise CountModelError("Validation actuals contain duplicate district-month keys.")
        origin = pd.Period(training["period"].max(), freq="M")
        target_periods = pd.period_range(origin + 1, periods=horizon, freq="M")
        indexed = training.set_index(["district", "period"])
        actual_index = actuals.set_index(["district", "period"])
        output = []
        for step, period in enumerate(target_periods, start=1):
            prior_period = str(period - 12)
            actual_period = str(period)
            for district in sorted(training["district"].unique()):
                key = (district, prior_period)
                actual_key = (district, actual_period)
                if key not in indexed.index or actual_key not in actual_index.index:
                    raise CountModelError(
                        f"Seasonal Naive needs previous-year value and actual for "
                        f"{district}/{actual_period}."
                    )
                mean = float(indexed.loc[key, "cases"])
                actual = int(actual_index.loc[actual_key, "cases"])
                draws = np.maximum(0, np.rint(mean + self.residuals))
                lower80, upper80 = np.quantile(draws, [0.10, 0.90])
                lower95, upper95 = np.quantile(draws, [0.025, 0.975])
                output.append({
                    "district": district,
                    "period": actual_period,
                    "horizon": step,
                    "actual": actual,
                    "predictive_mean": mean,
                    "predictive_variance": float(np.var(draws, ddof=1)),
                    "prediction_interval_80_lower": float(lower80),
                    "prediction_interval_80_upper": float(upper80),
                    "prediction_interval_95_lower": float(lower95),
                    "prediction_interval_95_upper": float(upper95),
                    "predictive_log_score": None,
                    "predictive_distribution": "empirical_seasonal_residual_intervals",
                })
        return output


def model_readiness() -> list[dict[str, Any]]:
    try:
        import pymc  # noqa: F401
    except ImportError:
        bayesian_status = "unavailable"
        bayesian_reason = (
            "PyMC/Stan are not installed; no Bayesian sampler is available to produce "
            "posterior convergence and effective-sample diagnostics."
        )
    else:
        bayesian_status = "not_evaluated"
        bayesian_reason = (
            "A sampler is present, but a separate model specification and diagnostic "
            "pilot are required before a defensible fit."
        )
    return [
        {
            "model_name": "seasonal_naive",
            "model_version": "1.0",
            "status": "evaluated",
            "reason": "Same-month previous-year benchmark; intervals use training-only pooled seasonal residuals.",
            "task": "count_forecasting",
            "requirements": ["At least 12 training months", "Same source category across the training series"],
            "limitations": ["Empirical interval distribution; predictive log score unavailable."],
        },
        {
            "model_name": "poisson_regression",
            "model_version": "1.0",
            "status": "evaluated",
            "reason": "Regularized pooled Poisson count regression with district and month effects.",
            "task": "count_forecasting",
            "requirements": ["Non-negative integer count target", "Training-only lagged features"],
            "limitations": ["Common dispersion assumption; estimated means may be overdispersed."],
        },
        {
            "model_name": "negative_binomial_regression",
            "model_version": "1.0",
            "status": "evaluated",
            "reason": "Regularized pooled NB2 likelihood with jointly estimated dispersion.",
            "task": "count_forecasting",
            "requirements": ["Non-negative integer count target", "Training-only lagged features"],
            "limitations": ["Fixed-effect pooling, not a Bayesian hierarchical model."],
        },
        {
            "model_name": "hierarchical_bayesian_negative_binomial",
            "model_version": None,
            "status": bayesian_status,
            "reason": bayesian_reason,
            "task": "count_forecasting",
            "requirements": [
                "Regularizing priors", "Multiple chains", "R-hat", "effective sample size",
                "Divergence checks", "Prior/posterior predictive checks",
            ],
            "limitations": [
                "No posterior samples or Bayesian performance claims are produced."
            ],
        },
    ]
