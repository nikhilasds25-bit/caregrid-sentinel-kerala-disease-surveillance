from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from caregrid.model_intelligence.evaluation import (
    evaluate_predictions,
    load_prediction_file,
    uncertainty_review,
    validate_equivalent_observations,
)
from caregrid.model_intelligence.interfaces import TASK_METRIC_CONTRACTS
from caregrid.model_intelligence.registry import build_default_registry
from caregrid.model_intelligence.selection import SelectionPolicy, select_models

ROOT = Path(__file__).resolve().parents[1]
SAVED_PREDICTIONS = ROOT / "reports" / "multimodel_experiment" / "predictions.csv"


def _synthetic_predictions(origins: int = 6) -> pd.DataFrame:
    rows = []
    for origin_index in range(origins):
        for district_index in range(14):
            actual = district_index
            for model_name, feature_set, bias, width in (
                ("accurate", "history", 0.0, 2.0),
                ("biased", "history", 4.0, 20.0),
            ):
                prediction = actual + bias
                lower80 = max(0, actual - width)
                upper80 = actual + width
                if model_name == "accurate" and district_index < 3:
                    lower80 = actual + 1
                lower95 = max(0, actual - width * 2)
                upper95 = actual + width * 2
                rows.append({
                    "model_name": model_name,
                    "model_version": "1.0",
                    "disease": "Dengue",
                    "classification": "Dashboard Confirmed",
                    "district": f"district-{district_index:02d}",
                    "geographic_level": "district",
                    "origin_period": f"{2018 + origin_index}-12",
                    "target_period": f"{2019 + origin_index}-01",
                    "horizon": 1,
                    "actual": actual,
                    "predictive_mean": prediction,
                    "predictive_variance": 1.0,
                    "prediction_interval_80_lower": lower80,
                    "prediction_interval_80_upper": upper80,
                    "prediction_interval_95_lower": lower95,
                    "prediction_interval_95_upper": upper95,
                    "predictive_log_score": -1.0,
                    "feature_set": feature_set,
                    "validation_phase": "rolling_origin",
                    "validation_window_id": f"rolling_origin-{2018 + origin_index}-12",
                })
    return pd.DataFrame(rows)


def test_registry_covers_current_models_and_unimplemented_extension_points():
    registry = build_default_registry()
    assert "poisson_regression::disease_history" in registry
    assert "negative_binomial_regression::disease_history_and_climate" in registry
    assert registry["seasonal_naive::disease_history"].predictive_uncertainty.startswith(
        "empirical"
    )
    assert (
        registry["bayesian_negative_binomial::planned"].readiness_status
        == "unavailable_inference_dependency"
    )
    assert registry["bayesian_poisson::planned"].readiness_status == "planned_not_implemented"
    assert registry["gaussian_process::planned"].readiness_status == "planned_not_implemented"
    assert registry["ensemble_forecast::planned"].readiness_status == "planned_not_implemented"
    assert "retrospective_unusual_activity_detection" in TASK_METRIC_CONTRACTS
    assert "probabilistic_outbreak_threshold_exceedance" in TASK_METRIC_CONTRACTS


def test_evaluator_scores_metrics_by_fold_district_and_horizon():
    predictions = _synthetic_predictions()
    result = evaluate_predictions(predictions)
    pooled = result.overall_metrics[result.overall_metrics["scope"].eq("pooled_district_months")]
    assert len(pooled) == 2
    accurate = pooled[pooled["model_name"].eq("accurate")].iloc[0]
    assert accurate["mae"] == pytest.approx(0.0)
    assert accurate["coverage_80"] == pytest.approx(11 / 14)
    assert accurate["interval_score_80"] >= accurate["mean_width_80"]
    assert len(result.fold_metrics) == 12
    assert result.fold_metrics["validation_window_id"].nunique() == 6
    assert result.overall_metrics["scope"].eq("district").any()
    assert len(result.residuals) == len(predictions)


def test_candidate_comparisons_reject_unequal_observation_sets_or_actuals():
    predictions = _synthetic_predictions()
    assert validate_equivalent_observations(predictions) == len(predictions)

    missing_observation = predictions.drop(index=0)
    with pytest.raises(ValueError, match="Unequal validation observations"):
        validate_equivalent_observations(missing_observation)

    inconsistent_actuals = predictions.copy()
    inconsistent_actuals.loc[0, "actual"] += 1
    with pytest.raises(ValueError, match="Observed values differ"):
        validate_equivalent_observations(inconsistent_actuals)


def test_selector_uses_calibration_gates_and_returns_insufficient_evidence():
    predictions = _synthetic_predictions()
    evaluation = evaluate_predictions(predictions)
    policy = SelectionPolicy(required_horizons=(1,))
    decisions, candidates = select_models(predictions, evaluation, policy)
    assert decisions.iloc[0]["selection_status"] == "selected_experimental"
    assert decisions.iloc[0]["selected_model_name"] == "accurate"
    assert set(candidates["eligibility_status"]) == {"eligible", "ineligible"}

    short_history = _synthetic_predictions(origins=4)
    short_evaluation = evaluate_predictions(short_history)
    short_decisions, _ = select_models(short_history, short_evaluation, policy)
    assert short_decisions.iloc[0]["selection_status"] == "insufficient_evidence"


def test_uncertainty_review_distinguishes_rolling_and_final_holdout_phases():
    predictions = _synthetic_predictions()
    final = predictions.copy()
    final["validation_phase"] = "final_2025"
    final["validation_window_id"] = "final_2025-2024-12"
    combined = pd.concat([predictions, final], ignore_index=True)
    review = uncertainty_review(combined)
    assert set(review["validation_phase"]) == {"rolling_origin", "final_2025"}
    assert review.loc[review["validation_phase"].eq("final_2025"), "n_origins"].eq(1).all()


def test_existing_experiment_integration_is_aligned_and_selection_ignores_2025():
    predictions = load_prediction_file(SAVED_PREDICTIONS)
    assert len(predictions) == 11760
    assert validate_equivalent_observations(predictions) == len(predictions)
    evaluation = evaluate_predictions(predictions)
    decisions, _ = select_models(predictions, evaluation)
    assert len(decisions) == 8
    assert set(decisions["selection_status"]).issubset(
        {"selected_experimental", "insufficient_evidence"}
    )

    changed_final = predictions.copy()
    final_mask = changed_final["validation_phase"].eq("final_2025")
    changed_final.loc[final_mask, "actual"] += 10000
    changed_decisions, _ = select_models(changed_final, evaluation)
    compare_columns = [
        "disease",
        "horizon",
        "selection_status",
        "selected_candidate_id",
        "reason",
    ]
    pd.testing.assert_frame_equal(
        decisions[compare_columns].reset_index(drop=True),
        changed_decisions[compare_columns].reset_index(drop=True),
    )


def test_integration_uncertainty_review_reports_undercoverage_from_saved_outputs():
    predictions = load_prediction_file(SAVED_PREDICTIONS)
    review = uncertainty_review(predictions, phases=("rolling_origin",))
    dengue_poisson_12 = review[
        review["disease"].eq("Dengue")
        & review["model_name"].eq("poisson_regression")
        & review["feature_set"].eq("disease_history")
        & review["horizon"].eq(12)
    ].iloc[0]
    assert dengue_poisson_12["coverage_assessment_80"] == "undercoverage"
    assert dengue_poisson_12["coverage_assessment_95"] == "undercoverage"
    assert dengue_poisson_12["n_origins"] == 6


def test_saved_experiment_prediction_output_is_not_rewritten_by_evaluation():
    before = SAVED_PREDICTIONS.stat().st_mtime_ns
    predictions = load_prediction_file(SAVED_PREDICTIONS)
    evaluate_predictions(predictions)
    assert SAVED_PREDICTIONS.stat().st_mtime_ns == before
