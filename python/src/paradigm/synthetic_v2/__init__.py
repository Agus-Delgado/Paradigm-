"""
Generador sintético v2 — verdad conocida y dificultad controlable.

No escribe archivos al importar. No modifica `data/synthetic/` (v1).
"""

from __future__ import annotations

from paradigm.synthetic_v2.calibrate import CalibrationError, CalibrationResult, calibrate_beta0_bisection
from paradigm.synthetic_v2.contracts import (
    POST_OUTCOME_COLUMNS,
    PREDECISIONAL_COLUMNS,
    TRUTH_COLUMNS,
    GenerationResult,
    GeneratorConfig,
    GeneratorTruth,
    ScenarioId,
    ValidationMetrics,
)
from paradigm.synthetic_v2.defaults import config_for_scenario, default_moderate_config
from paradigm.synthetic_v2.generate import generate_dataset
from paradigm.synthetic_v2.intervention import (
    INTERVENTION_ASSIGNMENT_COLUMNS,
    INTERVENTION_TRUTH_COLUMNS,
    InterventionParams,
)
from paradigm.synthetic_v2.runner import run_generation
from paradigm.synthetic_v2.validate import evaluate_multiseed, fingerprint_frames, validate_generation

__all__ = [
    "POST_OUTCOME_COLUMNS",
    "PREDECISIONAL_COLUMNS",
    "TRUTH_COLUMNS",
    "INTERVENTION_ASSIGNMENT_COLUMNS",
    "INTERVENTION_TRUTH_COLUMNS",
    "CalibrationError",
    "CalibrationResult",
    "GenerationResult",
    "GeneratorConfig",
    "GeneratorTruth",
    "InterventionParams",
    "ScenarioId",
    "ValidationMetrics",
    "calibrate_beta0_bisection",
    "config_for_scenario",
    "default_moderate_config",
    "evaluate_multiseed",
    "fingerprint_frames",
    "generate_dataset",
    "run_generation",
    "validate_generation",
]
