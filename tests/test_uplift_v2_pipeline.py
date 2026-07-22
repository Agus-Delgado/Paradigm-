"""Tests del pipeline uplift Two-Model (policy_intervention)."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "python" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from paradigm.ml_v2.features import (  # noqa: E402
    FORBIDDEN_FEATURE_COLUMNS,
    assert_no_leakage,
    build_model_frame,
)
from paradigm.ml_v2.uplift_metrics import (  # noqa: E402
    policy_value_curves,
    qini_metrics,
    true_benefit_from_ite_probability,
    uplift_by_decile,
    uplift_score_from_probs,
)
from paradigm.ml_v2.uplift_train import (  # noqa: E402
    TREATMENT_COLUMN,
    run_uplift_training_v2,
    select_uplift_model,
)
from paradigm.synthetic_v2.intervention import (  # noqa: E402
    INTERVENTION_ASSIGNMENT_COLUMNS,
    INTERVENTION_TRUTH_COLUMNS,
)

DATA_ROOT = ROOT / "data" / "synthetic_v2"
DATASET_ID = "policy_intervention_seed42"
FACT = DATA_ROOT / DATASET_ID / "fact_appointment.csv"
HAS_DATA = FACT.is_file()


class TestUpliftMetrics(unittest.TestCase):
    def test_uplift_score_and_true_benefit(self) -> None:
        p0 = np.array([0.2, 0.4, 0.3])
        p1 = np.array([0.1, 0.35, 0.25])
        uplift = uplift_score_from_probs(p0, p1)
        np.testing.assert_allclose(uplift, [0.1, 0.05, 0.05])
        ite = p1 - p0
        benefit = true_benefit_from_ite_probability(ite)
        np.testing.assert_allclose(benefit, uplift)

    def test_qini_perfect_beats_random(self) -> None:
        rng = np.random.default_rng(0)
        benefits = rng.normal(0.05, 0.02, size=200)
        perfect = qini_metrics(benefits, benefits)
        shuffled = benefits.copy()
        rng.shuffle(shuffled)
        randomish = qini_metrics(shuffled, benefits)
        self.assertGreater(perfect["qini_coefficient"], randomish["qini_coefficient"])
        self.assertGreater(perfect["qini_coefficient"], 0.9)

    def test_policy_value_model_vs_baselines(self) -> None:
        scores = np.array([0.9, 0.8, 0.1, 0.0])
        benefits = np.array([0.2, 0.15, 0.01, 0.0])
        pv = policy_value_curves(scores, benefits, fractions=(0.5, 1.0))
        top = pv["model"][0]["mean_true_benefit"]
        rand = pv["random"][0]["mean_true_benefit"]
        self.assertGreater(top, rand)
        self.assertEqual(pv["treat_none"][0]["mean_true_benefit"], 0.0)
        self.assertAlmostEqual(pv["treat_all"][0]["mean_true_benefit"], float(benefits.mean()))

    def test_uplift_by_decile_ordering(self) -> None:
        scores = np.linspace(1.0, 0.0, 100)
        benefits = scores * 0.1
        rows = uplift_by_decile(scores, benefits, n_deciles=10)
        self.assertEqual(rows[0]["decile"], 1)
        self.assertGreater(rows[0]["mean_predicted_uplift"], rows[-1]["mean_predicted_uplift"])


class TestUpliftLeakage(unittest.TestCase):
    def test_treatment_and_truth_forbidden(self) -> None:
        for col in list(INTERVENTION_TRUTH_COLUMNS) + list(INTERVENTION_ASSIGNMENT_COLUMNS):
            self.assertIn(col, FORBIDDEN_FEATURE_COLUMNS)
        with self.assertRaises(ValueError):
            assert_no_leakage(["lead_time_days", "true_ite_probability"])
        with self.assertRaises(ValueError):
            assert_no_leakage(["lead_time_days", TREATMENT_COLUMN])

    @unittest.skipUnless(HAS_DATA, "policy_intervention dataset missing")
    def test_model_frame_excludes_treatment_and_truth(self) -> None:
        from paradigm.ml_v2.dataset import load_eligible_v2

        df = load_eligible_v2(DATASET_ID, data_root=DATA_ROOT)
        X, y = build_model_frame(df)
        assert_no_leakage(X.columns)
        self.assertNotIn(TREATMENT_COLUMN, X.columns)
        self.assertNotIn("true_ite_probability", X.columns)
        self.assertNotIn("true_y0", X.columns)
        self.assertTrue(set(y.unique()).issubset({0, 1}))


@unittest.skipUnless(HAS_DATA, "policy_intervention dataset missing")
class TestUpliftPipeline(unittest.TestCase):
    def test_reproducibility_same_seed(self) -> None:
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            s1 = run_uplift_training_v2(
                dataset_id=DATASET_ID,
                out_dir=Path(a),
                data_root=DATA_ROOT,
                seed=42,
            )
            s2 = run_uplift_training_v2(
                dataset_id=DATASET_ID,
                out_dir=Path(b),
                data_root=DATA_ROOT,
                seed=42,
            )
            q1 = s1["metrics"]["random_forest"]["qini"]["qini_coefficient"]
            q2 = s2["metrics"]["random_forest"]["qini"]["qini_coefficient"]
            self.assertAlmostEqual(q1, q2, places=10)
            p1 = Path(a) / "predictions" / "test_uplift_predictions.csv"
            p2 = Path(b) / "predictions" / "test_uplift_predictions.csv"
            h1 = hashlib.sha256(p1.read_bytes()).hexdigest()
            h2 = hashlib.sha256(p2.read_bytes()).hexdigest()
            self.assertEqual(h1, h2)

    def test_run_registers_experiment(self) -> None:
        from scripts.train_uplift_v2 import run_uplift_v2_pipeline

        with tempfile.TemporaryDirectory() as tmp:
            run, summary = run_uplift_v2_pipeline(
                dataset_id=DATASET_ID,
                seed=42,
                runs_dir=Path(tmp),
                data_root=DATA_ROOT,
            )
            self.assertEqual(run.metadata.status, "completed")
            self.assertTrue((run.run_dir / "metrics.json").is_file())
            self.assertTrue((run.run_dir / "report.md").is_file())
            self.assertTrue((run.run_dir / "config.json").is_file())
            self.assertTrue(
                (run.run_dir / "predictions" / "test_uplift_predictions.csv").is_file()
            )
            for name in (
                "uplift_logistic_control.joblib",
                "uplift_logistic_treated.joblib",
                "uplift_rf_control.joblib",
                "uplift_rf_treated.joblib",
            ):
                self.assertTrue((run.run_dir / "models" / name).is_file())

            metrics = json.loads((run.run_dir / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(metrics.get("approach"), "two_model")
            self.assertFalse(metrics.get("cost_policy_connected"))
            selected = summary["selected_model"]
            self.assertIn(selected, ("logistic_regression", "random_forest"))
            q = summary["metrics"][selected]["qini"]["qini_coefficient"]
            self.assertIsInstance(q, float)

            cfg = json.loads((run.run_dir / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(cfg["experiment_type"], "causality")

    def test_select_uplift_model_prefers_higher_qini(self) -> None:
        chosen = select_uplift_model(
            {
                "logistic_regression": {"qini": {"qini_coefficient": 0.1}},
                "random_forest": {"qini": {"qini_coefficient": 0.4}},
            }
        )
        self.assertEqual(chosen, "random_forest")


if __name__ == "__main__":
    unittest.main()
