"""Tests de política de umbral (costos, capacidad, selección)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "python" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paradigm.ml_v2.threshold_policy import (  # noqa: E402
    ThresholdCostConfig,
    evaluate_threshold,
    select_best_threshold,
    sweep_thresholds,
)


class TestThresholdCosts(unittest.TestCase):
    def test_cost_benefit_net_value(self) -> None:
        # scores: high for first three; y = [1,0,1,1,0]
        y = np.array([1, 0, 1, 1, 0])
        s = np.array([0.9, 0.8, 0.7, 0.2, 0.1])
        cfg = ThresholdCostConfig(
            cost_fp=2.0,
            cost_fn=4.0,
            benefit_per_avoided=10.0,
            max_interventions=10,
        )
        # threshold 0.5 → intervene idx 0,1,2 → TP={0,2}, FP={1}, FN={3}
        row = evaluate_threshold(y, s, 0.5, cfg)
        self.assertEqual(row["tp"], 2)
        self.assertEqual(row["fp"], 1)
        self.assertEqual(row["fn"], 1)
        self.assertEqual(row["n_intervened"], 3)
        self.assertAlmostEqual(row["total_cost"], 2.0 * 1 + 4.0 * 1)
        self.assertAlmostEqual(row["expected_benefit"], 10.0 * 2)
        self.assertAlmostEqual(row["net_value"], 20.0 - 6.0)


class TestCapacityConstraint(unittest.TestCase):
    def test_capacity_limits_interventions(self) -> None:
        y = np.array([1, 0, 1, 0, 1, 0])
        s = np.array([0.95, 0.9, 0.85, 0.8, 0.75, 0.1])
        cfg = ThresholdCostConfig(
            cost_fp=1.0,
            cost_fn=1.0,
            benefit_per_avoided=3.0,
            max_interventions=2,
        )
        row = evaluate_threshold(y, s, 0.5, cfg)
        self.assertEqual(row["n_intervened"], 2)
        self.assertTrue(row["capacity_binding"])
        # Top-2 by score: y=[1,0] → tp=1,fp=1
        self.assertEqual(row["tp"], 1)
        self.assertEqual(row["fp"], 1)

    def test_fraction_capacity(self) -> None:
        y = np.zeros(100, dtype=int)
        y[:10] = 1
        s = np.linspace(1.0, 0.0, 100)
        cfg = ThresholdCostConfig(
            max_interventions=None,
            max_intervention_fraction=0.1,
            cost_fp=1.0,
            cost_fn=1.0,
            benefit_per_avoided=1.0,
        )
        self.assertEqual(cfg.resolved_capacity(100), 10)
        row = evaluate_threshold(y, s, 0.0, cfg)
        self.assertEqual(row["n_intervened"], 10)


class TestThresholdSelection(unittest.TestCase):
    def test_selects_max_net_value(self) -> None:
        y = np.array([1, 0, 1, 0, 1, 0, 0, 0])
        s = np.array([0.9, 0.85, 0.7, 0.65, 0.4, 0.3, 0.2, 0.1])
        cfg = ThresholdCostConfig(
            cost_fp=1.0,
            cost_fn=5.0,
            benefit_per_avoided=10.0,
            max_interventions=3,
        )
        rows = sweep_thresholds(y, s, cfg, thresholds=[0.2, 0.5, 0.8])
        best = select_best_threshold(rows)
        max_net = max(float(r["net_value"]) for r in rows)
        self.assertAlmostEqual(float(best["net_value"]), max_net)
        # Empate de net → mayor F1, luego menor n_intervened, luego mayor threshold
        tied = [r for r in rows if float(r["net_value"]) == max_net]
        expected = sorted(
            tied,
            key=lambda r: (float(r["f1"]), -int(r["n_intervened"]), float(r["threshold"])),
            reverse=True,
        )[0]
        self.assertEqual(best["threshold"], expected["threshold"])


if __name__ == "__main__":
    unittest.main()
