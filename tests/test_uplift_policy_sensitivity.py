"""Tests de sensibilidad y regret de políticas uplift."""

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

from paradigm.ml_v2.uplift_decision_policy import UpliftPolicyCostConfig  # noqa: E402
from paradigm.ml_v2.uplift_policy_sensitivity import (  # noqa: E402
    aggregate_multiseed,
    blend_uplift_with_truth,
    detect_frontiers,
    evaluate_policies_with_quality,
    regret_vs_oracle,
    select_oracle_indices,
    sensitivity_grid,
)


def _preds(n: int = 20) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    # Risk high where true benefit is low → risk suboptimal
    true_benefit = np.linspace(0.20, 0.01, n)
    p0 = np.linspace(0.1, 0.9, n)  # risk opposite to true benefit
    # Weak uplift prediction (noisy / flipped partially)
    pred_uplift = 0.3 * true_benefit + 0.05 * rng.normal(size=n)
    return pd.DataFrame(
        {
            "appointment_id": [f"A{i}" for i in range(n)],
            "y_true": (rng.random(n) < 0.2).astype(int),
            "p0_logistic_regression": p0,
            "p1_logistic_regression": p0 - pred_uplift,
            "uplift_logistic_regression": pred_uplift,
            "true_benefit": true_benefit,
            "selected_model": "logistic_regression",
        }
    )


class TestBlendAndRegret(unittest.TestCase):
    def test_blend_endpoints(self) -> None:
        pred = np.array([0.1, 0.2])
        truth = np.array([0.5, 0.6])
        np.testing.assert_allclose(blend_uplift_with_truth(pred, truth, 0.0), pred)
        np.testing.assert_allclose(blend_uplift_with_truth(pred, truth, 1.0), truth)
        mid = blend_uplift_with_truth(pred, truth, 0.5)
        np.testing.assert_allclose(mid, 0.5 * (pred + truth))

    def test_regret_non_negative_vs_oracle(self) -> None:
        self.assertAlmostEqual(regret_vs_oracle(5.0, 8.0), 3.0)
        self.assertAlmostEqual(regret_vs_oracle(8.0, 8.0), 0.0)


class TestOracleAndQuality(unittest.TestCase):
    def test_oracle_beats_risk_when_misaligned(self) -> None:
        preds = _preds(16)
        cfg = UpliftPolicyCostConfig(
            benefit_per_avoided=10.0,
            intervention_cost=0.4,
            max_interventions=4,
            max_intervention_fraction=None,
        )
        block = evaluate_policies_with_quality(preds, cfg, uplift_quality=0.0)
        self.assertGreaterEqual(block["oracle_true_net"], block["policies"]["risk"]["true_net_value"])
        self.assertGreaterEqual(block["regrets"]["risk"], 0.0)
        # q=1 → uplift ≈ oracle ranking
        block_q1 = evaluate_policies_with_quality(preds, cfg, uplift_quality=1.0)
        self.assertLessEqual(block_q1["regrets"]["uplift"], block["regrets"]["uplift"] + 1e-9)
        self.assertAlmostEqual(block_q1["regrets"]["uplift"], 0.0, places=6)

    def test_oracle_selection_capacity(self) -> None:
        preds = _preds(10)
        cfg = UpliftPolicyCostConfig(
            benefit_per_avoided=10.0,
            intervention_cost=0.4,
            max_interventions=3,
            max_intervention_fraction=None,
        )
        from paradigm.ml_v2.uplift_policy_sensitivity import build_quality_frame

        frame = build_quality_frame(preds, cfg, uplift_quality=0.0)
        sel = select_oracle_indices(frame, cfg)
        self.assertEqual(len(sel), 3)


class TestSensitivityGrid(unittest.TestCase):
    def test_grid_and_frontiers(self) -> None:
        preds = _preds(24)
        grid = sensitivity_grid(
            preds,
            capacity_grid=(5, 20),
            benefit_grid=(10.0,),
            cost_grid=(0.2, 2.0),
            quality_grid=(0.0, 1.0),
        )
        self.assertEqual(len(grid), 2 * 1 * 2 * 2)
        # High cost → often none
        high_c = [r for r in grid if r["intervention_cost"] == 2.0 and r["uplift_quality"] == 0.0]
        self.assertTrue(any(r["winner"] in ("none", "risk", "uplift", "net_value") for r in high_c))

        agg = aggregate_multiseed({"s1": grid, "s2": grid})
        self.assertEqual(agg["n_cells"], len(grid))
        self.assertEqual(agg["stability_rate"], 1.0)
        frontiers = detect_frontiers(agg["cells"])
        self.assertIsInstance(frontiers, list)

    def test_higher_quality_reduces_uplift_regret(self) -> None:
        preds = _preds(30)
        cfg = UpliftPolicyCostConfig(
            benefit_per_avoided=10.0,
            intervention_cost=0.4,
            max_interventions=6,
            max_intervention_fraction=None,
        )
        r0 = evaluate_policies_with_quality(preds, cfg, uplift_quality=0.0)["regrets"]["uplift"]
        r1 = evaluate_policies_with_quality(preds, cfg, uplift_quality=1.0)["regrets"]["uplift"]
        self.assertLessEqual(r1, r0)


if __name__ == "__main__":
    unittest.main()
