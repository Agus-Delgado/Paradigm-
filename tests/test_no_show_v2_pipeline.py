"""Tests del pipeline no-show v2 (synthetic_v2), sin alterar v1."""

from __future__ import annotations

import hashlib
import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "python" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from paradigm.ml_v2.dataset import load_eligible_v2  # noqa: E402
from paradigm.ml_v2.features import (  # noqa: E402
    FORBIDDEN_FEATURE_COLUMNS,
    PREDECISIONAL_CATEGORICAL,
    PREDECISIONAL_NUMERIC,
    assert_no_leakage,
    build_model_frame,
)
from paradigm.ml_v2.train import run_training_v2, temporal_split_by_appointment_date  # noqa: E402
from scripts.train_no_show_v2 import run_no_show_v2_pipeline  # noqa: E402

DATASET = "signal_moderate_seed42"
DATA_ROOT = ROOT / "data" / "synthetic_v2"


@unittest.skipUnless(
    (DATA_ROOT / DATASET / "fact_appointment.csv").is_file(),
    f"Missing {DATASET} under data/synthetic_v2",
)
class TestNoShowV2LeakageAndSplit(unittest.TestCase):
    def test_forbidden_columns_not_in_model_frame(self) -> None:
        df = load_eligible_v2(DATASET, data_root=DATA_ROOT)
        x, y = build_model_frame(df)
        assert_no_leakage(x.columns)
        for col in FORBIDDEN_FEATURE_COLUMNS:
            self.assertNotIn(col, x.columns)
        self.assertEqual(set(x.columns), set(PREDECISIONAL_CATEGORICAL + PREDECISIONAL_NUMERIC))
        self.assertTrue(set(y.unique()).issubset({0, 1}))

    def test_assert_no_leakage_raises(self) -> None:
        with self.assertRaises(ValueError):
            assert_no_leakage(["lead_time_days", "true_no_show_probability"])

    def test_temporal_split_no_future_leak(self) -> None:
        df = load_eligible_v2(DATASET, data_root=DATA_ROOT)
        train, test, cutoff = temporal_split_by_appointment_date(df, test_ratio=0.2)
        self.assertLessEqual(train["appointment_date"].max().strftime("%Y-%m-%d"), cutoff)
        self.assertGreater(test["appointment_date"].min().strftime("%Y-%m-%d"), cutoff)
        self.assertTrue(set(train["appointment_id"]).isdisjoint(set(test["appointment_id"])))


@unittest.skipUnless(
    (DATA_ROOT / DATASET / "fact_appointment.csv").is_file(),
    f"Missing {DATASET} under data/synthetic_v2",
)
class TestNoShowV2Training(unittest.TestCase):
    def test_reproducibility_same_seed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a = run_training_v2(
                dataset_id=DATASET,
                out_dir=Path(tmp) / "a",
                data_root=DATA_ROOT,
                seed=42,
            )
            b = run_training_v2(
                dataset_id=DATASET,
                out_dir=Path(tmp) / "b",
                data_root=DATA_ROOT,
                seed=42,
            )
            self.assertEqual(
                a["metrics"]["random_forest"]["roc_auc"],
                b["metrics"]["random_forest"]["roc_auc"],
            )
            self.assertEqual(
                a["metrics"]["baseline_logistic"]["brier"],
                b["metrics"]["baseline_logistic"]["brier"],
            )
            pred_a = Path(a["predictions_path"]).read_bytes()
            pred_b = Path(b["predictions_path"]).read_bytes()
            self.assertEqual(hashlib.sha256(pred_a).hexdigest(), hashlib.sha256(pred_b).hexdigest())

    def test_full_run_registers_experiment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run, summary = run_no_show_v2_pipeline(
                dataset_id=DATASET,
                seed=42,
                runs_dir=Path(tmp) / "runs",
                data_root=DATA_ROOT,
            )
            self.assertEqual(run.metadata.status, "completed")
            self.assertTrue((run.run_dir / "metrics.json").is_file())
            self.assertTrue((run.run_dir / "report.md").is_file())
            self.assertTrue((run.run_dir / "models" / "no_show_random_forest.joblib").is_file())
            self.assertTrue((run.run_dir / "predictions" / "test_predictions.csv").is_file())
            metrics = json.loads((run.run_dir / "metrics.json").read_text(encoding="utf-8"))
            rf = metrics["models"]["random_forest"]
            for key in (
                "roc_auc",
                "pr_auc",
                "brier",
                "log_loss",
                "precision",
                "recall",
                "f1",
                "top_decile",
            ):
                self.assertIn(key, rf, msg=key)
            self.assertEqual(summary["selected_model"], "random_forest")
            self.assertIsNotNone(summary["true_p_reference"]["roc_auc"])


class TestNoShowV1Preserved(unittest.TestCase):
    def test_v1_train_entrypoints_untouched(self) -> None:
        import paradigm.ml.train as v1_train
        import scripts.train_no_show as v1_script

        self.assertTrue(hasattr(v1_train, "run_training"))
        sig = inspect.signature(v1_train.run_training)
        self.assertIn("db_path", sig.parameters)
        self.assertTrue(hasattr(v1_script, "run_no_show_pipeline"))
        # v2 must not be the module that v1 script imports for training
        src = Path(v1_script.__file__).read_text(encoding="utf-8")
        self.assertIn("from paradigm.ml.train import run_training", src)
        self.assertNotIn("paradigm.ml_v2", src)
        self.assertNotIn("run_training_v2", src)


if __name__ == "__main__":
    unittest.main()
