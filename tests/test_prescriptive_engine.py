"""Tests del motor prescriptivo unificado."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "python" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from paradigm.prescriptive import (  # noqa: E402
    PrescriptiveConfig,
    run_prescriptive_engine,
)
from paradigm.prescriptive.policy_selector import select_operating_policy  # noqa: E402


def _risk_frame(n: int = 20) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    risk = np.linspace(0.9, 0.1, n)
    return pd.DataFrame(
        {
            "appointment_id": [f"A{i}" for i in range(n)],
            "proba_random_forest": risk,
            "y_true": (rng.random(n) < risk).astype(int),
        }
    )


def _uplift_frame(n: int = 20) -> pd.DataFrame:
    risk = np.linspace(0.9, 0.1, n)
    uplift = np.linspace(0.20, 0.01, n)
    return pd.DataFrame(
        {
            "appointment_id": [f"A{i}" for i in range(n)],
            "proba_random_forest": risk,
            "uplift_selected": uplift,
            "p0_random_forest": risk,
            "p1_random_forest": risk - uplift,
        }
    )


class TestPolicySelection(unittest.TestCase):
    def test_default_risk_when_quality_low(self) -> None:
        cfg = PrescriptiveConfig(uplift_quality=0.2, intervention_cost=0.4, benefit_per_avoided=10.0)
        sel = select_operating_policy(cfg, has_uplift=True, mean_estimated_uplift=0.05)
        self.assertEqual(sel["policy"], "risk")

    def test_uplift_when_quality_high(self) -> None:
        cfg = PrescriptiveConfig(uplift_quality=0.8, intervention_cost=0.4, benefit_per_avoided=10.0)
        sel = select_operating_policy(cfg, has_uplift=True, mean_estimated_uplift=0.05)
        self.assertEqual(sel["policy"], "uplift")

    def test_none_when_cost_exceeds_benefit(self) -> None:
        cfg = PrescriptiveConfig(
            uplift_quality=0.9,
            intervention_cost=5.0,
            benefit_per_avoided=10.0,
            assumed_ate=0.05,
        )
        sel = select_operating_policy(cfg, has_uplift=True, mean_estimated_uplift=0.05)
        self.assertEqual(sel["policy"], "none")
        self.assertTrue(sel["economic_gate_blocked"])

    def test_forced_policy(self) -> None:
        cfg = PrescriptiveConfig(forced_policy="random", intervention_cost=100.0)
        sel = select_operating_policy(cfg, has_uplift=False)
        self.assertEqual(sel["policy"], "random")


class TestCapacityAndFallback(unittest.TestCase):
    def test_capacity_limits_interventions(self) -> None:
        preds = _risk_frame(50)
        cfg = PrescriptiveConfig(
            max_interventions=5,
            max_intervention_fraction=None,
            uplift_quality=0.0,
            intervention_cost=0.4,
            benefit_per_avoided=10.0,
        )
        result = run_prescriptive_engine(preds, cfg)
        self.assertEqual(result.policy_used, "risk")
        self.assertEqual(result.n_intervened, 5)
        self.assertEqual(result.capacity, 5)

    def test_fallback_none_high_cost(self) -> None:
        preds = _risk_frame(30)
        cfg = PrescriptiveConfig(
            intervention_cost=10.0,
            benefit_per_avoided=10.0,
            assumed_ate=0.05,
            uplift_quality=0.0,
            max_interventions=10,
        )
        result = run_prescriptive_engine(preds, cfg)
        self.assertEqual(result.policy_used, "none")
        self.assertEqual(result.n_intervened, 0)

    def test_uplift_policy_uses_uplift_ranking(self) -> None:
        preds = _uplift_frame(12)
        cfg = PrescriptiveConfig(
            uplift_quality=0.9,
            max_interventions=3,
            max_intervention_fraction=None,
            intervention_cost=0.4,
            benefit_per_avoided=10.0,
        )
        result = run_prescriptive_engine(preds, cfg)
        self.assertEqual(result.policy_used, "uplift")
        intervened = result.recommendations[
            result.recommendations["recommended_action"] == "intervene"
        ]
        self.assertEqual(len(intervened), 3)
        # Top uplift ids should be A0,A1,A2
        self.assertEqual(set(intervened["appointment_id"]), {"A0", "A1", "A2"})


class TestOutputFormat(unittest.TestCase):
    def test_recommendation_schema(self) -> None:
        preds = _risk_frame(15)
        cfg = PrescriptiveConfig(max_interventions=4, max_intervention_fraction=None)
        result = run_prescriptive_engine(preds, cfg)
        required = {
            "appointment_id",
            "recommended_action",
            "risk_score",
            "uplift",
            "expected_net_value",
            "priority",
            "explanation",
            "policy_used",
            "uncertainty",
        }
        self.assertTrue(required.issubset(result.recommendations.columns))
        row = result.recommendations.iloc[0].to_dict()
        self.assertIn(row["recommended_action"], ("intervene", "do_not_intervene"))
        self.assertIsInstance(row["explanation"], str)
        self.assertIsInstance(row["uncertainty"], dict)
        self.assertIn("risk", result.comparison)
        self.assertIn("uplift", result.comparison)
        self.assertIn("net_value", result.comparison)
        self.assertIn("none", result.comparison)


if __name__ == "__main__":
    unittest.main()
