"""Reusable registry, evaluation, and experimental selection for CareGrid models."""

from caregrid.model_intelligence.evaluation import (
    EvaluationResult,
    evaluate_predictions,
    validate_equivalent_observations,
)
from caregrid.model_intelligence.registry import ModelRegistration, build_default_registry
from caregrid.model_intelligence.selection import (
    SelectionPolicy,
    select_models,
)

__all__ = [
    "EvaluationResult",
    "ModelRegistration",
    "SelectionPolicy",
    "build_default_registry",
    "evaluate_predictions",
    "select_models",
    "validate_equivalent_observations",
]
