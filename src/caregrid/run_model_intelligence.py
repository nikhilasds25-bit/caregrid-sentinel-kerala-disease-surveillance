"""Evaluate saved experiment predictions without fitting or modifying forecasts."""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from caregrid.model_intelligence.evaluation import (
    evaluate_predictions,
    load_prediction_file,
    uncertainty_review,
    validate_equivalent_observations,
)
from caregrid.model_intelligence.registry import build_default_registry
from caregrid.model_intelligence.selection import SelectionPolicy, select_models

EXPERIMENT_DIR = PROJECT_ROOT / "reports" / "multimodel_experiment"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "model_intelligence"
REPORT_DIR = PROJECT_ROOT / "reports"


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(_jsonable(value), indent=2, allow_nan=False),
        encoding="utf-8",
    )


def _coverage_table(review: pd.DataFrame, phase: str, disease: str | None = None) -> str:
    data = review[
        review["validation_phase"].eq(phase)
        & review["horizon"].isin([1, 3, 6, 12])
    ]
    if disease:
        data = data[data["disease"].eq(disease)]
    columns = [
        "disease",
        "model_name",
        "feature_set",
        "horizon",
        "n_predictions",
        "n_origins",
        "coverage_80",
        "coverage_95",
        "mean_width_80",
        "mean_width_95",
        "coverage_assessment_80",
        "coverage_assessment_95",
    ]
    if data.empty:
        return "No interval predictions available."
    frame = data[columns].copy()
    for column in ("coverage_80", "coverage_95"):
        frame[column] = frame[column].map(
            lambda value: f"{value:.1%}" if pd.notna(value) else "Unavailable"
        )
    for column in ("mean_width_80", "mean_width_95"):
        frame[column] = frame[column].map(
            lambda value: f"{value:.2f}" if pd.notna(value) else "Unavailable"
        )
    headers = list(frame.columns)
    rows = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    rows.extend(
        "| " + " | ".join(str(value) for value in row) + " |"
        for row in frame.itertuples(index=False, name=None)
    )
    return "\n".join(rows)


def _selection_table(decisions: pd.DataFrame) -> str:
    frame = decisions[
        [
            "disease",
            "horizon",
            "selection_status",
            "selected_candidate_id",
            "eligible_candidate_count",
            "score_margin",
            "reason",
        ]
    ].copy()
    frame["score_margin"] = frame["score_margin"].map(
        lambda value: f"{value:.3f}" if pd.notna(value) else "N/A"
    )
    headers = list(frame.columns)
    rows = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    rows.extend(
        "| " + " | ".join(str(value) for value in row) + " |"
        for row in frame.itertuples(index=False, name=None)
    )
    return "\n".join(rows)


def _report(
    predictions: pd.DataFrame,
    decisions: pd.DataFrame,
    candidate_stats: pd.DataFrame,
    review: pd.DataFrame,
    provenance: dict[str, Any],
) -> str:
    rolling = review[review["validation_phase"].eq("rolling_origin")]
    final = review[review["validation_phase"].eq("final_2025")]
    failures_path = EXPERIMENT_DIR / "model_failures.csv"
    failures = pd.read_csv(failures_path) if failures_path.exists() else pd.DataFrame()
    failure_count = len(failures)
    selected_count = int(decisions["selection_status"].eq("selected_experimental").sum())
    rolling_under80 = int(rolling["coverage_assessment_80"].eq("undercoverage").sum())
    rolling_under95 = int(rolling["coverage_assessment_95"].eq("undercoverage").sum())
    rolling_over80 = int(rolling["coverage_assessment_80"].eq("overcoverage").sum())
    rolling_over95 = int(rolling["coverage_assessment_95"].eq("overcoverage").sum())
    return f"""# Model selection and uncertainty validation

## Scope and input integrity

This evaluation reads saved predictions only. It does not retrain models or write to the existing experiment directory. Input: `reports/multimodel_experiment/predictions.csv`, SHA-256 `{provenance['prediction_sha256']}`. Original experiment metadata reports disease-candidate SHA-256 `{provenance['disease_candidate_sha256']}` and weather-candidate SHA-256 `{provenance['weather_candidate_sha256']}`.

All eligible model/feature candidates were checked against identical disease, classification, geographic level, validation phase/window, origin, target period, district, and horizon keys, with exactly matching actual counts. The saved prediction file contains {len(predictions):,} records; {int(predictions['validation_phase'].eq('rolling_origin').sum()):,} development rolling-origin records and {int(predictions['validation_phase'].eq('final_2025').sum()):,} final-2025 records. Saved experiment fit/forecast failures: {failure_count}.

## Experimental selection method

Selection is performed independently for Dengue and Leptospirosis at horizons 1, 3, 6, and 12 months. Only `rolling_origin` records are used; the 2025 final holdout is excluded. A candidate must have at least 5 rolling origins and 70 equivalent predictions, both 80% and 95% predictive intervals, aggregate coverage within 10 percentage points of nominal, per-origin minimum coverage of at least 50% (80% intervals) and 70% (95% intervals), and fold MAE coefficient of variation no greater than 2.0.

Eligible candidates are ranked on a prespecified composite: 40% average MAE/RMSE rank, 40% average proper 80%/95% interval-score rank (which penalizes both misses and unnecessarily wide intervals), and 20% fold-MAE-variability rank. If the best two candidates are within 0.10 composite-score units, the engine returns `insufficient_evidence` rather than forcing a winner. A unique eligible candidate can be selected only after passing the same uncertainty and stability gates.

The selection policy is an experimental evidence filter, not an automated production model-switching policy. Six rolling origins are limited evidence, and nearby annual origins are not equivalent to six independent trials.

## Selection results

{_selection_table(decisions)}

Selected experimentally: {selected_count} of {len(decisions)} disease/horizon combinations. These statuses are comparative outputs only; they do not establish clinical readiness or disease-definition consistency.

## Rolling-origin predictive interval review

The nominal 80% and 95% quantities are **predictive intervals** for future counts, not confidence intervals for model parameters or the mean. Coverage tolerance is used to flag undercoverage (more than 10 percentage points below nominal) and overcoverage (more than 10 points above nominal). Overcoverage can indicate overly wide intervals; interval-score ranking penalizes this.

{_coverage_table(review, 'rolling_origin')}

Across the 120 rolling model/disease/horizon summaries (all 12 horizons), 80% intervals are flagged undercovered in {rolling_under80} groups and 95% intervals in {rolling_under95}; overcoverage flags occur in {rolling_over80} 80% groups and {rolling_over95} 95% groups. Undercoverage indicates intervals are too narrow or otherwise miss more often than the nominal level suggests; it is a warning of overconfident predictive uncertainty, especially for longer-horizon Dengue and Poisson variants. Some Seasonal Naive and short-horizon Leptospirosis intervals overcover, with very large widths. Model/horizon-specific results and widths are in `reports/model_intelligence/uncertainty_review.csv`. Coverage is calculated over district predictions pooled across origins; origin-level minima are also used as a selection gate. This is diagnostic evidence, not proof of calibrated uncertainty.

## Final 2025 holdout (descriptive only)

The following summaries are reported for transparency, but were not used for eligibility, scoring, or selection. At each horizon there is one origin and 14 district observations per disease/model, too little to establish calibration.

{_coverage_table(review, 'final_2025')}

## Limits

All experiment outputs remain exploratory because historical dashboard classification consistency has not been officially established. Uncertainty summaries assess empirical coverage only; they do not establish prospective calibration. No confidence intervals are implied by predictive intervals. No outbreak labels or official thresholds were evaluated. Forecasting, retrospective unusual-activity detection, and outbreak threshold-exceedance probability remain distinct tasks.
"""


def _architecture_report(registry: dict[str, Any]) -> str:
    entries = list(registry.values())
    active = [entry for entry in entries if entry["readiness_status"] != "planned_not_implemented"]
    planned = [entry for entry in entries if entry["readiness_status"] == "planned_not_implemented"]
    rows = []
    for item in entries:
        rows.append(
            "| {model} | {task} | {status} | {uncertainty} |".format(
                model=item["model_id"],
                task=item["analytical_task"],
                status=item["readiness_status"],
                uncertainty=item["predictive_uncertainty"],
            )
        )
    return f"""# CareGrid Model Intelligence and Evaluation Engine

## Purpose and current boundary

The engine is a reusable offline layer for registering model capability, validating comparable prediction sets, calculating task-specific metrics, and making explicitly gated experimental selections. It consumes saved predictions and does not train models. The existing forecasting experiment, source datasets, daily IDSP pipeline, and live dashboard are outside its write path.

## Registry

Each registration records stable model ID, name/version, analytical task, supported diseases, required features, training requirements, supported horizon, prediction-output contract, uncertainty availability, readiness, failure status, and limitations. Each implemented feature configuration is a distinct registry entry so climate and history-only results cannot be confused. Registry serialization is in `reports/model_intelligence/model_registry.json`.

| Model / configuration | Analytical task | Readiness | Uncertainty |
|---|---|---|---|
{chr(10).join(rows)}

Current evaluated forecast configurations: {sum(entry['readiness_status'] == 'evaluated_exploratory' for entry in active)}; Bayesian Negative Binomial is registered as unavailable because no PyMC/Stan runtime is installed; outbreak probability is blocked pending thresholds and labels. Algorithm extension points marked planned: {len(planned)}. Planned registrations do not indicate that a model has been implemented or evaluated.

## Common evaluation contract

`evaluation.py` verifies required prediction fields, non-negative counts, interval ordering, unique keys, and equivalent observation keys and actuals across every model/feature candidate. Metrics are emitted overall, by district, by horizon, and by rolling-origin window:

- MAE, RMSE, and mean Poisson deviance for count errors.
- Predictive log score when a distributional score exists; missing scores remain unavailable.
- 80%/95% predictive interval coverage, mean width, and proper interval score.
- Per-fold MAE, coverage, interval score, and stability inputs.

The 2025 final period is available for descriptive holdout reporting only. It is not used in candidate scoring or model selection.

## Selection behavior

`selection.py` applies explicit sample-size, origin-count, interval-coverage, per-origin stability, and forecast-error stability gates, then ranks eligible candidates on accuracy (40%), interval score (40%), and fold MAE variability (20%). A close composite tie returns `insufficient_evidence`; a candidate with unreliable intervals cannot win merely through lower MAE. Policy values and per-candidate rejection reasons are persisted with the selection results. No result should be treated as a live model route without independent review.

## Extension interfaces and analytical task boundaries

`interfaces.py` defines separate contracts and output types:

1. `ForecastingModel` predicts future counts and is evaluated with forecast error, count scoring, and predictive-interval metrics.
2. `UnusualActivityDetector` identifies retrospective deviations from a defined baseline and requires independently reviewed unusual-activity labels for sensitivity, specificity, precision-recall, and false-alert-rate evaluation.
3. `OutbreakProbabilityEstimator` estimates probability of exceeding a versioned epidemiological threshold and requires both a specified threshold and verified outbreak labels; it is evaluated with Brier score, log loss, and reliability/calibration metrics.

These are not interchangeable. The engine does not create alerts or infer official thresholds. Bayesian Negative Binomial is explicitly marked unavailable because the inference runtime is missing; Bayesian Poisson, Gaussian Process, Student-t Process, Bayesian Structural Time Series, Hidden Markov, and ensemble registrations are extension points only. No such algorithms are implemented here.

## Known limitations

- Current validation has six rolling origins and a single 2025 final origin; coverage is not established prospectively.
- Candidate counts derive from Kerala Health Department dashboard classifications whose historical semantic consistency remains unresolved.
- District weather features are from representative locations, not district-wide averages.
- Existing model intervals are evaluated as predictive intervals. No parameter confidence intervals are in this evaluation.
- The engine's model ranking is experimental, non-clinical, and not wired to the dashboard.
"""


def run_evaluation(
    experiment_dir: Path = EXPERIMENT_DIR,
    output_dir: Path = OUTPUT_DIR,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    prediction_path = experiment_dir / "predictions.csv"
    predictions = load_prediction_file(prediction_path)
    equivalent_observations = validate_equivalent_observations(predictions)
    evaluation = evaluate_predictions(predictions)
    policy = SelectionPolicy()
    decisions, candidate_stats = select_models(predictions, evaluation, policy)
    review = uncertainty_review(predictions)

    registry = build_default_registry()
    model_failures_path = experiment_dir / "model_failures.csv"
    model_failures = (
        pd.read_csv(model_failures_path)
        if model_failures_path.exists() else pd.DataFrame()
    )
    if not model_failures.empty:
        failed_keys = set(
            zip(model_failures["model_name"], model_failures["feature_set"])
        )
        for model_id, entry in registry.items():
            if (entry.model_name, model_id.split("::", 1)[1]) in failed_keys:
                registry[model_id] = replace(
                    entry,
                    readiness_status="failed_in_experiment",
                    failure_status="one_or_more_fit_or_forecast_failures",
                )
    registry_json = {key: value.as_dict() for key, value in registry.items()}
    experiment_metadata_path = experiment_dir / "experiment_metadata.json"
    experiment_metadata = json.loads(experiment_metadata_path.read_text(encoding="utf-8"))
    provenance = {
        "prediction_sha256": __import__("hashlib").sha256(
            prediction_path.read_bytes()
        ).hexdigest(),
        "disease_candidate_sha256": experiment_metadata["input_hashes"][
            "disease_candidate_sha256"
        ],
        "weather_candidate_sha256": experiment_metadata["input_hashes"][
            "weather_candidate_sha256"
        ],
    }

    evaluation.overall_metrics.to_csv(output_dir / "evaluation_by_group.csv", index=False)
    evaluation.fold_metrics.to_csv(output_dir / "rolling_origin_fold_metrics.csv", index=False)
    evaluation.residuals.to_csv(output_dir / "scored_predictions_and_residuals.csv", index=False)
    decisions.to_csv(output_dir / "model_selection.csv", index=False)
    candidate_stats.to_csv(output_dir / "candidate_selection_diagnostics.csv", index=False)
    review.to_csv(output_dir / "uncertainty_review.csv", index=False)
    _write_json(output_dir / "model_registry.json", registry_json)
    _write_json(output_dir / "selection_policy.json", asdict(policy))
    _write_json(
        output_dir / "evaluation_metadata.json",
        {
            "source_experiment_directory": str(
                experiment_dir.resolve().relative_to(PROJECT_ROOT)
            ),
            "prediction_file_sha256": provenance["prediction_sha256"],
            "equivalent_observation_records_validated": equivalent_observations,
            "selection_uses_validation_phase": "rolling_origin",
            "final_holdout_used_for_selection": False,
            "model_failure_rows": len(model_failures),
        },
    )
    (REPORT_DIR / "model_intelligence_architecture.md").write_text(
        _architecture_report(registry_json), encoding="utf-8"
    )
    (REPORT_DIR / "model_selection_validation.md").write_text(
        _report(predictions, decisions, candidate_stats, review, provenance),
        encoding="utf-8",
    )
    return {
        "status": "completed",
        "equivalent_observation_records": equivalent_observations,
        "selection_decisions": len(decisions),
        "selected_experimental": int(
            decisions["selection_status"].eq("selected_experimental").sum()
        ),
        "insufficient_evidence": int(
            decisions["selection_status"].eq("insufficient_evidence").sum()
        ),
        "output_directory": str(output_dir),
    }


def main() -> int:
    result = run_evaluation()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
