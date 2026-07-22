"""Motor prescriptivo unificado para decisiones de no-show (sin UI)."""

from __future__ import annotations

from paradigm.prescriptive.config import PrescriptiveConfig, SUPPORTED_POLICIES
from paradigm.prescriptive.engine import (
    PrescriptiveResult,
    build_recommendations,
    compare_policies_summary,
    run_prescriptive_engine,
)
from paradigm.prescriptive.policy_selector import select_operating_policy

__all__ = [
    "SUPPORTED_POLICIES",
    "PrescriptiveConfig",
    "PrescriptiveResult",
    "build_recommendations",
    "compare_policies_summary",
    "run_prescriptive_engine",
    "select_operating_policy",
]
