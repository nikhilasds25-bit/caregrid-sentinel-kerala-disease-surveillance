"""Run a controlled, offline rolling-origin disease-count experiment."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from caregrid.multimodel.data import DISEASES, ModelDataError, load_model_ready_data
from caregrid.multimodel.metrics import calculate_metrics
from caregrid.multimodel.models import (
    CountModelError,
    NegativeBinomialCountModel,
    PoissonCountModel,
    SeasonalNaiveModel,
    model_readiness,
)
from caregrid.multimodel.types import ExperimentSpec, PredictiveOutput, ValidationWindow

OUTPUT_DIR = PROJECT_ROOT / "reports" / "multimodel_experiment"
REPORT_DIR = PROJECT_ROOT / "reports"
FORECAST_HORIZON = 12
ROLLING_ORIGINS = tuple(f"{year}-12" for year in range(2018, 2024))
FINAL_ORIGIN = "2024-12"


def _relative(path: str) -> str:
    try:
        return str(Path(path).resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return Path(path).name


def _model_scenarios() -> list[tuple[str, bool, str, dict[str, Any]]]:
    return [
        ("seasonal_naive", False, "disease_history", {"residual_years": 3}),
        ("poisson_regression", False, "disease_history", {"alpha": 0.1}),
        ("negative_binomial_regression", False, "disease_history", {"ridge_alpha": 0.1}),
        ("poisson_regression", True, "disease_history_and_climate", {"alpha": 0.1}),
        (
            "negative_binomial_regression",
            True,
            "disease_history_and_climate",
            {"ridge_alpha": 0.1},
        ),
    ]


def _new_model(name: str) -> Any:
    if name == "seasonal_naive":
        return SeasonalNaiveModel()
    if name == "poisson_regression":
        return PoissonCountModel(alpha=0.1)
    if name == "negative_binomial_regression":
        return NegativeBinomialCountModel(ridge_alpha=0.1)
    raise ValueError(f"Unknown experiment model: {name}")


def _window(origin: str, phase: str) -> ValidationWindow:
    start = str(pd.Period(origin, freq="M") + 1)
    end = str(pd.Period(origin, freq="M") + FORECAST_HORIZON)
    return ValidationWindow(
        window_id=f"{phase}-{origin}",
        phase=phase,
        origin_period=origin,
        target_start=start,
        target_end=end,
        horizon_months=FORECAST_HORIZON,
    )


def _run_one_window(
    panel: pd.DataFrame,
    disease: str,
    origin: str,
    phase: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    disease_panel = panel[panel["disease"].eq(disease)].copy()
    origin_period = pd.Period(origin, freq="M")
    training = disease_panel[disease_panel["period"].le(str(origin_period))].copy()
    target_periods = [
        str(period)
        for period in pd.period_range(
            origin_period + 1, periods=FORECAST_HORIZON, freq="M"
        )
    ]
    actuals = disease_panel[disease_panel["period"].isin(target_periods)].copy()
    if set(actuals["period"].unique()) != set(target_periods):
        raise ModelDataError(f"Missing target months for {disease}, origin {origin}.")
    window = _window(origin, phase)
    records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    fit_configurations: list[dict[str, Any]] = []
    for name, climate, feature_set, _configuration in _model_scenarios():
        model = _new_model(name)
        try:
            model.fit(training, climate=climate)
            raw_predictions = model.forecast(
                training,
                FORECAST_HORIZON,
                climate=climate,
                actuals=actuals,
            )
            fitted_parameters: dict[str, Any] = {}
            if isinstance(model, PoissonCountModel):
                fitted_parameters = {
                    "alpha": model.alpha,
                    "coefficients": model.estimator.coef_.tolist(),
                    "coefficient_names": list(model.encoder.columns),
                }
            elif isinstance(model, NegativeBinomialCountModel):
                fitted_parameters = {
                    "ridge_alpha": model.ridge_alpha,
                    "dispersion_alpha": model.dispersion_alpha,
                    "coefficients": model.coefficients.tolist(),
                    "coefficient_names": list(model.encoder.columns),
                }
            elif isinstance(model, SeasonalNaiveModel):
                fitted_parameters = {
                    "residual_years": model.residual_years,
                    "residual_count": int(len(model.residuals)),
                }
            fit_configurations.append({
                "disease": disease,
                "model_name": name,
                "model_version": model.version,
                "feature_set": feature_set,
                "validation_phase": phase,
                "origin_period": origin,
                "training_start": str(training["period"].min()),
                "training_end": str(training["period"].max()),
                "training_rows": int(model.n_training_rows),
                "parameters": fitted_parameters,
            })
        except (CountModelError, ModelDataError, ValueError, FloatingPointError) as error:
            failures.append({
                "disease": disease,
                "model_name": name,
                "feature_set": feature_set,
                "origin_period": origin,
                "validation_phase": phase,
                "error_type": type(error).__name__,
                "error": str(error),
            })
            continue

        specification = ExperimentSpec(
            experiment_name="kerala_confirmed_district_monthly_forecast_comparison",
            experiment_version="1.0.0",
            disease=disease,
            classification="Dashboard Confirmed",
            geographic_level="district",
            forecast_horizon=FORECAST_HORIZON,
            input_dataset="data/candidates/kerala_district_monthly_disease_dashboard_2016_2025.csv",
            input_sha256=str(panel.attrs["provenance"]["disease_candidate_sha256"]),
            feature_configuration={
                "feature_set": feature_set,
                "numeric_predictors": (
                    ["trend_years", "log_lag_cases"]
                    + (
                        [
                            "previous-month rainfall",
                            "preceding-three-month rainfall sum",
                            "previous-month mean temperature",
                            "previous-month temperature range",
                            "previous-month relative humidity",
                            "previous-month dew point",
                        ]
                        if climate else []
                    )
                ),
                "categorical_predictors": ["district", "month_of_year"],
                "forecast_weather": "weather features frozen at forecast origin",
            },
            validation_period=f"{window.target_start} to {window.target_end}",
        )
        for item in raw_predictions:
            output = PredictiveOutput(
                model_name=name,
                model_version=model.version,
                disease=disease,
                classification="Dashboard Confirmed",
                district=item["district"],
                geographic_level="district",
                origin_period=origin,
                target_period=item["period"],
                horizon=item["horizon"],
                actual=item["actual"],
                predictive_mean=item["predictive_mean"],
                predictive_variance=item["predictive_variance"],
                prediction_interval_80_lower=item["prediction_interval_80_lower"],
                prediction_interval_80_upper=item["prediction_interval_80_upper"],
                prediction_interval_95_lower=item["prediction_interval_95_lower"],
                prediction_interval_95_upper=item["prediction_interval_95_upper"],
                predictive_log_score=item["predictive_log_score"],
                feature_set=feature_set,
                validation_phase=phase,
                limitations=(
                    ["Empirical residual intervals; log score not defined."]
                    if item["predictive_log_score"] is None else []
                ),
            )
            row = output.as_dict()
            row["validation_window_id"] = window.window_id
            row["predictive_distribution"] = item["predictive_distribution"]
            row["experiment_spec"] = json.dumps(specification.as_dict(), sort_keys=True)
            records.append(row)
    return records, failures, fit_configurations


def _save_plots(predictions: pd.DataFrame, metrics: pd.DataFrame, output_dir: Path) -> None:
    if predictions.empty:
        return
    pooled = metrics[
        metrics["scope"].eq("pooled_district_months")
        & metrics["validation_phase"].eq("rolling_origin")
    ]
    for disease in DISEASES:
        disease_metrics = pooled[pooled["disease"].eq(disease)]
        fig, ax = plt.subplots(figsize=(11, 6))
        for (model_name, feature_set), group in disease_metrics.groupby(
            ["model_name", "feature_set"]
        ):
            ax.plot(
                group.sort_values("horizon")["horizon"],
                group.sort_values("horizon")["mae"],
                marker="o",
                label=f"{model_name} ({feature_set.replace('_', ' ')})",
            )
        ax.set(title=f"{disease}: rolling-origin MAE by horizon", xlabel="Horizon (months)", ylabel="MAE (cases)")
        ax.legend()
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(output_dir / f"{disease.lower()}_rolling_mae.png", dpi=150)
        plt.close(fig)

    final = predictions[predictions["validation_phase"].eq("final_2025")].copy()
    if not final.empty:
        final["residual"] = final["actual"] - final["predictive_mean"]
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        for disease, group in final.groupby("disease"):
            axes[0].hist(group["residual"], bins=25, alpha=0.5, label=disease)
            axes[1].scatter(
                group["actual"],
                group["predictive_mean"],
                s=18,
                alpha=0.6,
                label=disease,
            )
        axes[0].set(title="Final-period residuals", xlabel="Actual - predicted cases", ylabel="Prediction count")
        axes[0].legend()
        axes[1].set(title="Final-period predictions", xlabel="Actual cases", ylabel="Predicted mean cases")
        axes[1].legend()
        axes[1].grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(output_dir / "final_2025_residuals_and_predictions.png", dpi=150)
        plt.close(fig)

        preferred = final[
            final["model_name"].eq("negative_binomial_regression")
            & final["feature_set"].eq("disease_history")
        ]
        if not preferred.empty:
            monthly = preferred.groupby(["disease", "target_period"], as_index=False).agg(
                actual=("actual", "sum"),
                predicted_mean=("predictive_mean", "sum"),
                lower80_sum=("prediction_interval_80_lower", "sum"),
                upper80_sum=("prediction_interval_80_upper", "sum"),
            )
            fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
            for axis, disease in zip(axes, DISEASES):
                group = monthly[monthly["disease"].eq(disease)].sort_values("target_period")
                axis.plot(group["target_period"], group["actual"], marker="o", label="Observed")
                axis.plot(group["target_period"], group["predicted_mean"], marker="o", label="Predicted mean")
                axis.fill_between(
                    np.arange(len(group)),
                    group["lower80_sum"].to_numpy(),
                    group["upper80_sum"].to_numpy(),
                    alpha=0.15,
                    label="Sum of district 80% interval endpoints",
                )
                axis.set_title(f"{disease} 2025 district-summed benchmark")
                axis.set_ylabel("Cases")
                axis.set_xticks(np.arange(len(group)), group["target_period"], rotation=45)
                axis.legend()
                axis.grid(alpha=0.2)
            fig.tight_layout()
            fig.savefig(output_dir / "final_2025_actual_predicted.png", dpi=150)
            plt.close(fig)


def _readiness_report(provenance: dict[str, Any], readiness: dict[str, Any]) -> str:
    candidate_hash = provenance["disease_candidate_sha256"]
    weather_hash = provenance["weather_candidate_sha256"]
    return f"""# Multi-model experiment data readiness

## Result

The separate dashboard-native Confirmed panel is structurally usable for an exploratory district-month comparison. This is not a finding that its disease definitions are stable over time or equivalent to DHS categories.

| Check | Result |
|---|---:|
| Districts | {provenance['district_count']} |
| Monthly periods | {provenance['period_count']} (2016-01 through 2025-12) |
| Confirmed disease rows | {provenance['confirmed_rows']} |
| Rows per disease | {json.dumps(readiness['confirmed_panel']['rows_per_disease'], sort_keys=True)} |
| Missing Confirmed counts | {provenance['confirmed_missing_cases']} |
| Explicit Confirmed zeros | {provenance['confirmed_zero_cases']} |
| Dashboard district/state case mismatch cells (all classifications) | {provenance['reconciliation_mismatch_cells']} |
| Confirmed mismatch cells | {provenance['confirmed_reconciliation_mismatch_cells']} |
| Confirmed district rows linked to a mismatch cell | {provenance['reconciliation_flagged_confirmed_rows']} |
| Disease-weather matched rows | {provenance['weather_matched_rows']} |

Suspected records are excluded from model targets and remain a distinct source-native classification. The DHS Probable category is not mapped to dashboard Suspected. All four source reconciliation mismatch cells remain in the reconciliation output; the two Confirmed mismatch cells are attached to each affected district row as flags. District observations were not adjusted.

## Source integrity

- Disease candidate: `data/candidates/kerala_district_monthly_disease_dashboard_2016_2025.csv`; SHA-256 `{candidate_hash}`.
- Source snapshot SHA-256: `{provenance['disease_source_sha256']}`.
- Weather candidate: `data/candidates/kerala_district_representative_weather_monthly_2016_2025.csv`; SHA-256 `{weather_hash}`.
- Reconciliation SHA-256: `{provenance['reconciliation_sha256']}`.
- Both candidate hashes and the reconciliation hash were verified by the loader against their sidecar metadata before the experiment.

## Feature readiness and limits

The history-only regressions use district, month-of-year, a linear time trend, and the previous month's Confirmed case count. Climate variants add origin-known previous-month rainfall, a preceding-three-month rainfall sum, mean temperature, temperature range, relative humidity, and dew point. Numerical features are standardized from each training fold only.

All 3,360 Confirmed district-month rows match complete representative-location weather rows. These weather data are single representative points per district, not district-wide areal averages. Climate predictors for each forecast are frozen at the forecast origin; no realized target-period weather is used.

No values were imputed, no source categories were merged, and no district-to-state discrepancies were corrected. The 2025 period is reserved as a final chronological holdout; it does not participate in fitting or model tuning.
"""


def _results_report(predictions: pd.DataFrame, metrics: pd.DataFrame, failures: pd.DataFrame) -> str:
    if metrics.empty:
        return "# Multi-model experiment\n\nNo model produced evaluable predictions. See `model_failures.csv`.\n"
    final = metrics[
        metrics["scope"].eq("pooled_district_months")
        & metrics["validation_phase"].eq("final_2025")
    ]
    rolling = metrics[
        metrics["scope"].eq("pooled_district_months")
        & metrics["validation_phase"].eq("rolling_origin")
    ]
    result_lines = []
    for disease in DISEASES:
        result_lines.append(f"### {disease}")
        disease_final = final[final["disease"].eq(disease)]
        if disease_final.empty:
            result_lines.append("No final-period model results were evaluable.")
        else:
            for horizon in (1, 3, 6, 12):
                group = disease_final[disease_final["horizon"].eq(horizon)]
                if group.empty:
                    continue
                best = group.sort_values("mae").iloc[0]
                result_lines.append(
                    f"- Final 2025, horizon {horizon}: lowest MAE was "
                    f"`{best['model_name']}` ({best['feature_set']}), "
                    f"MAE {best['mae']:.2f}, RMSE {best['rmse']:.2f}; "
                    f"80%/95% interval coverage "
                    f"{best['coverage_80']:.1%}/{best['coverage_95']:.1%} "
                    f"(n={int(best['n_predictions'])})."
                )
        disease_rolling = rolling[
            (rolling["disease"].eq(disease)) & (rolling["horizon"].eq(12))
        ]
        if not disease_rolling.empty:
            best = disease_rolling.sort_values("mae").iloc[0]
            result_lines.append(
                f"- Rolling-origin horizon-12 lowest MAE: `{best['model_name']}` "
                f"({best['feature_set']}), MAE {best['mae']:.2f} across "
                f"{int(best['n_predictions'])} district-month predictions."
            )

    climate_comparison = []
    for disease in DISEASES:
        subset = rolling[
            (rolling["disease"].eq(disease))
            & rolling["model_name"].isin(
                ["poisson_regression", "negative_binomial_regression"]
            )
        ]
        for model_name in subset["model_name"].unique():
            paired = subset[
                (subset["model_name"].eq(model_name))
                & subset["horizon"].isin([1, 3, 6, 12])
            ].pivot(index="horizon", columns="feature_set", values="mae")
            if {"disease_history", "disease_history_and_climate"}.issubset(paired.columns):
                delta = paired["disease_history_and_climate"] - paired["disease_history"]
                climate_comparison.append(
                    f"- {disease}, {model_name}: climate-minus-history MAE by horizon "
                    + ", ".join(f"{h}m {delta.loc[h]:+.2f}" for h in delta.index)
                    + " cases (negative favors climate)."
                )

    failure_note = (
        f"{len(failures)} model-window fits/forecasts failed and are recorded explicitly."
        if not failures.empty else "No model-window failures were recorded."
    )
    return f"""# Exploratory multi-model forecasting experiment

## Scope and validation

This is an offline retrospective experiment using Dashboard Confirmed district-month observations only. It is not a production forecasting or outbreak-warning system. Historical semantic consistency is not officially established; dashboard Confirmed is not equated with DHS Confirmed or Probable.

The models are Seasonal Naive, regularized Poisson regression, and regularized NB2 regression, each disease-history-only; Poisson and NB2 are also evaluated with a separate climate feature set. Forecasts are recursively generated at horizons 1–12. Development rolling origins are December 2018 through December 2023, each evaluated over the following 12 months. The untouched final evaluation is the single December 2024 origin forecasting January–December 2025. No random split is used. Hyperparameters were fixed in advance for this experiment; the rolling origins are comparative validation, not hyperparameter tuning.

Metrics include MAE, RMSE, mean Poisson deviance, predictive log score where a probability distribution is available, 80%/95% interval coverage and mean interval width. Metrics are also exported by district and horizon. Seasonal Naive uses pooled training-only seasonal residual intervals; its predictive log score is unavailable. The final period supplies only 14 district observations at each horizon per disease/model, so calibration estimates are imprecise.

## Results (lower MAE is better)

{chr(10).join(result_lines)}

### Climate increment

{chr(10).join(climate_comparison) if climate_comparison else "Paired climate/history metrics were unavailable."}

Climate benefit is determined empirically from matched rolling-origin MAE in `metrics.csv`; the feature family is not presumed useful. These results do not establish causal climate effects.

## Predictive uncertainty

Poisson and NB2 intervals are distributional intervals from their fitted count likelihoods; Seasonal Naive intervals are empirical residual intervals. Their realized coverage and width are reported in `metrics.csv`. Coverage is a retrospective summary, not proof of calibrated uncertainty. Reported disease-month results do not include a jointly calibrated statewide interval.

The final-period figure showing sums of district interval endpoints is descriptive only: summing marginal endpoints does not produce a valid joint statewide prediction interval.

## Bayesian model feasibility

Hierarchical Bayesian Negative Binomial was not implemented. The environment has no PyMC/Stan inference runtime, so posterior convergence, effective sample size, divergence, and predictive checks cannot be established. The implemented pooled NB2 is a fixed-effect frequentist model and is not a Bayesian substitute. See `model_readiness.json`.

## Outbreak intelligence

The experiment forecasts future counts only. Unusual-activity detection and outbreak-probability estimation remain separate tasks. No independently verified outbreak labels or official thresholds are available here; therefore no outbreak sensitivity, specificity, probability calibration, or lead-time claim is made.

{failure_note}

## Reproducibility

Machine-readable predictions, residuals, metrics, model configurations, model readiness, validation windows, plots, and input hashes are under `reports/multimodel_experiment/`. `data_readiness.json` records validated panel properties. Source discrepancies and district/state reconciliation flags remain intact and are never silently substituted or corrected.
"""


def run_experiment(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    panel, metadata = load_model_ready_data()
    panel.attrs["provenance"] = metadata["provenance"]

    windows = [
        _window(origin, "rolling_origin") for origin in ROLLING_ORIGINS
    ] + [_window(FINAL_ORIGIN, "final_2025")]
    predictions: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    fit_configurations: list[dict[str, Any]] = []
    for disease in DISEASES:
        for origin in ROLLING_ORIGINS:
            rows, errors, fitted = _run_one_window(
                panel, disease, origin, "rolling_origin"
            )
            predictions.extend(rows)
            failures.extend(errors)
            fit_configurations.extend(fitted)
        rows, errors, fitted = _run_one_window(
            panel, disease, FINAL_ORIGIN, "final_2025"
        )
        predictions.extend(rows)
        failures.extend(errors)
        fit_configurations.extend(fitted)

    prediction_frame = pd.DataFrame(predictions)
    failure_frame = pd.DataFrame(
        failures,
        columns=[
            "disease", "model_name", "feature_set", "origin_period",
            "validation_phase", "error_type", "error",
        ],
    )
    metric_frame = calculate_metrics(prediction_frame)
    prediction_frame.to_csv(output_dir / "predictions.csv", index=False)
    failure_frame.to_csv(output_dir / "model_failures.csv", index=False)
    metric_frame.to_csv(output_dir / "metrics.csv", index=False)
    if not prediction_frame.empty:
        residuals = prediction_frame.copy()
        residuals["residual"] = residuals["actual"] - residuals["predictive_mean"]
        residuals["absolute_error"] = residuals["residual"].abs()
        residuals.to_csv(output_dir / "residuals.csv", index=False)
    else:
        pd.DataFrame(columns=["residual", "absolute_error"]).to_csv(
            output_dir / "residuals.csv", index=False
        )

    configurations = []
    for model_name, climate, feature_set, parameters in _model_scenarios():
        configurations.append({
            "model_name": model_name,
            "model_version": "1.0",
            "feature_set": feature_set,
            "parameters": parameters,
            "features": (
                ["district", "month_of_year", "linear_trend", "previous_month_cases"]
                + (
                    [
                        "previous_month_rainfall",
                        "preceding_3_month_rainfall_sum",
                        "previous_month_mean_temperature",
                        "previous_month_temperature_range",
                        "previous_month_relative_humidity",
                        "previous_month_dew_point",
                    ] if climate else []
                )
            ),
        })
    provenance = metadata["provenance"]
    for key in ("disease_candidate_path", "disease_metadata_path", "reconciliation_path", "weather_candidate_path", "weather_metadata_path"):
        provenance[key] = _relative(provenance[key])
    data_readiness = {**metadata["readiness"], "provenance": provenance}
    (output_dir / "data_readiness.json").write_text(
        json.dumps(data_readiness, indent=2), encoding="utf-8"
    )
    (output_dir / "model_configurations.json").write_text(
        json.dumps(configurations, indent=2), encoding="utf-8"
    )
    (output_dir / "model_fit_configurations.json").write_text(
        json.dumps(fit_configurations, indent=2), encoding="utf-8"
    )
    (output_dir / "model_readiness.json").write_text(
        json.dumps(model_readiness(), indent=2), encoding="utf-8"
    )
    (output_dir / "validation_windows.json").write_text(
        json.dumps([window.as_dict() for window in windows], indent=2),
        encoding="utf-8",
    )
    (output_dir / "experiment_metadata.json").write_text(
        json.dumps(
            {
                "experiment_name": "kerala_confirmed_district_monthly_forecast_comparison",
                "experiment_version": "1.0.0",
                "classification": "Dashboard Confirmed",
                "input_hashes": {
                    "disease_candidate_sha256": provenance["disease_candidate_sha256"],
                    "disease_source_sha256": provenance["disease_source_sha256"],
                    "reconciliation_sha256": provenance["reconciliation_sha256"],
                    "weather_candidate_sha256": provenance["weather_candidate_sha256"],
                    "weather_source_batch_sha256": provenance["weather_source_batch_sha256"],
                },
                "forecast_horizon_months": FORECAST_HORIZON,
                "rolling_validation_origins": ROLLING_ORIGINS,
                "final_origin": FINAL_ORIGIN,
                "random_split": False,
                "weather_origin_rule": "Freeze observed weather features as of each forecast origin.",
                "exploratory_only": True,
                "disease_definition_consistency_established": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    _save_plots(prediction_frame, metric_frame, output_dir)
    (REPORT_DIR / "multimodel_data_readiness.md").write_text(
        _readiness_report(provenance, metadata["readiness"]),
        encoding="utf-8",
    )
    (REPORT_DIR / "multimodel_experiment_report.md").write_text(
        _results_report(prediction_frame, metric_frame, failure_frame),
        encoding="utf-8",
    )
    return {
        "status": "completed" if not prediction_frame.empty else "no_evaluable_predictions",
        "prediction_rows": int(len(prediction_frame)),
        "failure_rows": int(len(failure_frame)),
        "metrics_rows": int(len(metric_frame)),
        "output_dir": str(output_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    arguments = parser.parse_args()
    result = run_experiment(arguments.output_dir)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
