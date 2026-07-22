"""Tests de política de decisión uplift × costos."""

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

from paradigm.ml_v2.uplift_decision_policy import (  # noqa: E402
    UpliftPolicyCostConfig,
    build_decision_frame,
    compare_policies,
    evaluate_selection,
    select_indices,
)


def _toy_predictions(n: int = 10) -> pd.DataFrame:
    # risk/uplift constructed so net_value ordering differs from risk
    rng = np.random.default_rng(0)
    p0 = np.linspace(0.4, 0.1, n)
    uplift = np.array([0.20, 0.18, 0.05, 0.15, 0.02, 0.12, 0.01, 0.08, 0.03, 0.10][:n])
    p1 = p0 - uplift
    true_benefit = uplift * 0.9 + 0.01
    return pd.DataFrame(
        {
            "appointment_id": [f"A{i}" for i in range(n)],
            "y_true": (rng.random(n) < p0).astype(int),
            "p0_logistic_regression": p0,
            "p1_logistic_regression": p1,
            "uplift_logistic_regression": uplift,
            "true_benefit": true_benefit,
            "selected_model": "logistic_regression",
        }
    )


class TestValueCalculation(unittest.TestCase):
    def test_expected_net_value_formula(self) -> None:
        preds = _toy_predictions(5)
        cfg = UpliftPolicyCostConfig(
            benefit_per_avoided=10.0,
            intervention_cost=1.0,
            max_interventions=10,
            max_intervention_fraction=None,
        )
        frame = build_decision_frame(preds, cfg)
        # ENV = B * uplift - C
        expected = 10.0 * frame["uplift"] - 1.0
        np.testing.assert_allclose(frame["expected_net_value"], expected)
        np.testing.assert_allclose(frame["expected_benefit"], 10.0 * frame["uplift"])
        self.assertTrue((frame["intervention_cost"] == 1.0).all())
        self.assertIn("risk", frame.columns)


class TestCapacity(unittest.TestCase):
    def test_capacity_limits_selection(self) -> None:
        preds = _toy_predictions(10)
        cfg = UpliftPolicyCostConfig(
            benefit_per_avoided=10.0,
            intervention_cost=1.0,
            max_interventions=3,
            max_intervention_fraction=0.5,  # would be 5; min → 3
        )
        self.assertEqual(cfg.resolved_capacity(10), 3)
        frame = build_decision_frame(preds, cfg)
        for policy in ("random", "risk", "uplift", "net_value"):
            sel = select_indices(frame, policy, cfg)
            self.assertLessEqual(len(sel), 3)
            self.assertEqual(len(sel), 3)

    def test_none_and_treat_all_ignore_capacity_semantics(self) -> None:
        preds = _toy_predictions(8)
        cfg = UpliftPolicyCostConfig(max_interventions=2, max_intervention_fraction=0.1)
        frame = build_decision_frame(preds, cfg)
        self.assertEqual(len(select_indices(frame, "none", cfg)), 0)
        self.assertEqual(len(select_indices(frame, "treat_all", cfg)), 8)


class TestPolicyComparison(unittest.TestCase):
    def test_net_value_beats_risk_when_misaligned(self) -> None:
        # High risk but low uplift on first rows; high uplift on lower risk
        n = 6
        p0 = np.array([0.9, 0.85, 0.8, 0.3, 0.25, 0.2])
        uplift = np.array([0.01, 0.02, 0.01, 0.25, 0.22, 0.20])
        preds = pd.DataFrame(
            {
                "appointment_id": [f"A{i}" for i in range(n)],
                "y_true": [1, 1, 0, 0, 0, 0],
                "p0_random_forest": p0,
                "p1_random_forest": p0 - uplift,
                "uplift_random_forest": uplift,
                "true_benefit": uplift,
                "selected_model": "random_forest",
            }
        )
        cfg = UpliftPolicyCostConfig(
            benefit_per_avoided=10.0,
            intervention_cost=1.0,
            max_interventions=2,
            max_intervention_fraction=None,
            min_net_value=0.0,
        )
        result = compare_policies(preds, cfg)
        risk_sel = select_indices(build_decision_frame(preds, cfg), "risk", cfg)
        net_sel = select_indices(build_decision_frame(preds, cfg), "net_value", cfg)
        # Risk picks top risk (0,1); net picks high uplift (3,4)
        self.assertTrue(set(risk_sel.tolist()).issubset({0, 1, 2}))
        self.assertTrue(set(net_sel.tolist()).issubset({3, 4, 5}))
        self.assertGreater(
            result["policies"]["net_value"]["true_net_value"],
            result["policies"]["risk"]["true_net_value"],
        )
        self.assertIn(result["winner"], ("net_value", "uplift"))

    def test_evaluate_selection_costs(self) -> None:
        preds = _toy_predictions(4)
        cfg = UpliftPolicyCostConfig(
            benefit_per_avoided=10.0,
            intervention_cost=2.0,
            max_interventions=10,
            max_intervention_fraction=None,
        )
        frame = build_decision_frame(preds, cfg)
        sel = np.array([0, 1])
        row = evaluate_selection(frame, sel, cfg, policy="uplift")
        self.assertEqual(row["n_intervened"], 2)
        self.assertAlmostEqual(row["intervention_cost_total"], 4.0)
        self.assertAlmostEqual(
            row["predicted_net_value"],
            row["predicted_benefit"] - 4.0,
        )
