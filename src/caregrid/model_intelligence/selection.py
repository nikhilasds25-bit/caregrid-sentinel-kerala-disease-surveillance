"""Experimental selection with hard uncertainty and evidence gates."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from caregrid.model_intelligence.evaluation import EvaluationResult, validate_predictions


@dataclass(frozen=True)
class SelectionPolicy:
    required_horizons: tuple[int, ...] = (1, 3, 6, 12)
    minimum_rolling_origins: int = 5
    minimum_predictions: int = 70
    coverage_tolerance: float = 0.10
    minimum_fold_coverage_80: float = 0.50
    minimum_fold_coverage_95: float = 0.70
    maximum_fold_mae_cv: float = 2.0
    minimum_score_margin: float = 0.10
    require_both_interval_levels: bool = True


def _candidate_statistics(
    predictions: pd.DataFrame,
    evaluation: EvaluationResult,
    policy: SelectionPolicy,
) -> pd.DataFrame:
    development = predictions[predictions["validation_phase"].eq("rolling_origin")].copy()
    pooled = evaluation.overall_metrics[
        evaluation.overall_metrics["scope"].eq("pooled_district_months")
        & evaluation.overall_metrics["validation_phase"].eq("rolling_origin")
    ]
    folds = evaluation.fold_metrics[
        evaluation.fold_metrics["validation_phase"].eq("rolling_origin")
    ].copy()
    rows = []
    group_columns = ["disease", "horizon", "model_name", "feature_set"]
    for key, group in development.groupby(group_columns, sort=True, dropna=False):
        disease, horizon, model_name, feature_set = key
        matching = pooled[
            pooled["disease"].eq(disease)
            & pooled["horizon"].eq(horizon)
            & pooled["model_name"].eq(model_name)
            & pooled["feature_set"].eq(feature_set)
        ]
        if matching.empty:
            continue
        aggregate = matching.iloc[0]
        fold = folds[
            folds["disease"].eq(disease)
            & folds["horizon"].eq(horizon)
            & folds["model_name"].eq(model_name)
            & folds["feature_set"].eq(feature_set)
        ]
        fold_cv = (
            float(fold["mae"].std(ddof=1) / max(fold["mae"].mean(), 1e-12))
            if len(fold) > 1 else np.nan
        )
        row = {
            "disease": disease,
            "horizon": int(horizon),
            "model_name": model_name,
            "feature_set": feature_set,
            "candidate_id": f"{model_name}::{feature_set}",
            "n_predictions": int(len(group)),
            "n_origins": int(group["validation_window_id"].nunique()),
            "mae": float(aggregate["mae"]),
            "rmse": float(aggregate["rmse"]),
            "mean_poisson_deviance": float(aggregate["mean_poisson_deviance"]),
            "mean_predictive_log_score": float(aggregate["mean_predictive_log_score"]),
            "coverage_80": float(aggregate["coverage_80"]),
            "coverage_95": float(aggregate["coverage_95"]),
            "mean_width_80": float(aggregate["mean_width_80"]),
            "mean_width_95": float(aggregate["mean_width_95"]),
            "interval_score_80": float(aggregate["interval_score_80"]),
            "interval_score_95": float(aggregate["interval_score_95"]),
            "mean_fold_mae": float(fold["mae"].mean()) if len(fold) else np.nan,
            "fold_mae_sd": float(fold["mae"].std(ddof=1)) if len(fold) > 1 else np.nan,
            "fold_mae_cv": fold_cv,
            "minimum_fold_coverage_80": float(fold["coverage_80"].min()) if len(fold) else np.nan,
            "minimum_fold_coverage_95": float(fold["coverage_95"].min()) if len(fold) else np.nan,
            "fold_interval_score_80_mean": float(fold["interval_score_80"].mean()) if len(fold) else np.nan,
            "fold_interval_score_95_mean": float(fold["interval_score_95"].mean()) if len(fold) else np.nan,
        }
        reasons = []
        if row["n_origins"] < policy.minimum_rolling_origins:
            reasons.append("too_few_rolling_origins")
        if row["n_predictions"] < policy.minimum_predictions:
            reasons.append("too_few_equivalent_predictions")
        for level in (80, 95):
            coverage = row[f"coverage_{level}"]
            nominal = level / 100
            lower = nominal - policy.coverage_tolerance
            upper = min(1.0, nominal + policy.coverage_tolerance)
            if not np.isfinite(coverage):
                reasons.append(f"{level}_percent_intervals_unavailable")
            elif not lower <= coverage <= upper:
                direction = "under" if coverage < lower else "over"
                reasons.append(f"{direction}coverage_{level}_percent")
            fold_coverage = row[f"minimum_fold_coverage_{level}"]
            floor = (
                policy.minimum_fold_coverage_80
                if level == 80 else policy.minimum_fold_coverage_95
            )
            if not np.isfinite(fold_coverage) or fold_coverage < floor:
                reasons.append(f"unstable_fold_coverage_{level}_percent")
        if policy.require_both_interval_levels and (
            not np.isfinite(row["interval_score_80"])
            or not np.isfinite(row["interval_score_95"])
        ):
            reasons.append("proper_interval_scores_unavailable")
        if not np.isfinite(fold_cv) or fold_cv > policy.maximum_fold_mae_cv:
            reasons.append("unstable_fold_mae")
        row["eligibility_status"] = "eligible" if not reasons else "ineligible"
        row["eligibility_reasons"] = reasons
        rows.append(row)
    return pd.DataFrame(rows)


def select_models(
    predictions: pd.DataFrame,
    evaluation: EvaluationResult,
    policy: SelectionPolicy = SelectionPolicy(),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select separately by disease and horizon using development folds only.

    The 2025 final holdout is deliberately never read by this selector.
    """
    data = validate_predictions(predictions)
    stats = _candidate_statistics(data, evaluation, policy)
    decisions = []
    requested_diseases = sorted(data["disease"].unique())
    for disease in requested_diseases:
        for horizon in policy.required_horizons:
            group = stats[
                stats["disease"].eq(disease) & stats["horizon"].eq(horizon)
            ].copy()
            eligible = group[group["eligibility_status"].eq("eligible")].copy()
            decision = {
                "disease": disease,
                "horizon": horizon,
                "selection_status": "insufficient_evidence",
                "selected_candidate_id": None,
                "selected_model_name": None,
                "selected_feature_set": None,
                "eligible_candidate_count": int(len(eligible)),
                "evaluated_candidate_count": int(len(group)),
                "selection_score": np.nan,
                "runner_up_score": np.nan,
                "score_margin": np.nan,
                "selection_policy": str(asdict(policy)),
                "reason": "",
            }
            if eligible.empty:
                decision["reason"] = (
                    "No candidate met the minimum rolling-origin evidence, fold stability, "
                    "and interval-coverage requirements."
                )
                decisions.append(decision)
                continue

            # Rank all three dimensions within the eligible set; proper interval
            # scores penalize both missed observations and unnecessarily wide bands.
            eligible["accuracy_rank"] = (
                eligible["mae"].rank(method="average", pct=True)
                + eligible["rmse"].rank(method="average", pct=True)
            ) / 2
            eligible["uncertainty_rank"] = (
                eligible["interval_score_80"].rank(method="average", pct=True)
                + eligible["interval_score_95"].rank(method="average", pct=True)
            ) / 2
            eligible["stability_rank"] = eligible["fold_mae_cv"].rank(
                method="average", pct=True
            )
            eligible["selection_score"] = (
                0.40 * eligible["accuracy_rank"]
                + 0.40 * eligible["uncertainty_rank"]
                + 0.20 * eligible["stability_rank"]
            )
            eligible = eligible.sort_values(
                ["selection_score", "mae", "candidate_id"], kind="stable"
            ).reset_index(drop=True)
            winner = eligible.iloc[0]
            runner_up = eligible.iloc[1] if len(eligible) > 1 else None
            margin = (
                float(runner_up["selection_score"] - winner["selection_score"])
                if runner_up is not None else np.nan
            )
            if runner_up is not None and margin < policy.minimum_score_margin:
                decision["reason"] = (
                    "Eligible candidates are too close under the accuracy, interval-score, "
                    "and fold-stability composite; no winner is forced."
                )
                decision["selection_score"] = float(winner["selection_score"])
                decision["runner_up_score"] = float(runner_up["selection_score"])
                decision["score_margin"] = margin
            else:
                decision.update({
                    "selection_status": "selected_experimental",
                    "selected_candidate_id": winner["candidate_id"],
                    "selected_model_name": winner["model_name"],
                    "selected_feature_set": winner["feature_set"],
                    "selection_score": float(winner["selection_score"]),
                    "runner_up_score": (
                        float(runner_up["selection_score"])
                        if runner_up is not None else np.nan
                    ),
                    "score_margin": margin,
                    "reason": (
                        "Candidate passed coverage and fold-stability gates and ranked best "
                        "on the prespecified accuracy/interval-score/stability composite."
                    ),
                })
            decisions.append(decision)

            for index, row in eligible.iterrows():
                stats_index = stats.index[
                    (stats["disease"].eq(disease))
                    & (stats["horizon"].eq(horizon))
                    & (stats["candidate_id"].eq(row["candidate_id"]))
                ][0]
                stats.loc[stats_index, "selection_score"] = float(row["selection_score"])
                stats.loc[stats_index, "accuracy_rank"] = float(row["accuracy_rank"])
                stats.loc[stats_index, "uncertainty_rank"] = float(row["uncertainty_rank"])
                stats.loc[stats_index, "stability_rank"] = float(row["stability_rank"])
    return pd.DataFrame(decisions), stats
