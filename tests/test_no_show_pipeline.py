"""Tests for no-show pipeline integration with ml.experiments runs."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "python" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ml.experiments import load_run  # noqa: E402
from ml.experiments.store import read_json  # noqa: E402
from paradigm.io.paths import DB_PATH  # noqa: E402
from scripts.train_no_show import run_no_show_pipeline  # noqa: E402


class TestNoShowRunIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not DB_PATH.is_file():
            raise unittest.SkipTest(f"Mart missing: {DB_PATH}. Run build_sqlite_mart.py first.")

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        self.out_dir = self.tmp / "legacy_out"
        self.runs_dir = self.tmp / "runs"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_pipeline_creates_completed_run_with_metrics_and_predictions(self) -> None:
        run, summary = run_no_show_pipeline(
            db_path=DB_PATH,
            out_dir=self.out_dir,
            runs_dir=self.runs_dir,
        )

        self.assertTrue(run.run_dir.is_dir())
        self.assertTrue(str(run.run_dir).startswith(str(self.runs_dir)))
        self.assertNotIn(
            str(ROOT / "ml" / "experiments" / "runs"),
            str(run.run_dir.resolve()),
        )

        reloaded = load_run(run.run_dir)
        self.assertEqual(reloaded.metadata.status, "completed")
        self.assertIsNone(reloaded.metadata.error)

        metrics = reloaded.metrics
        self.assertIn("models", metrics)
        self.assertIn("baseline_logistic", metrics["models"])
        self.assertIn("random_forest", metrics["models"])
        self.assertIn("roc_auc", metrics["models"]["baseline_logistic"])
        self.assertIn("roc_auc", metrics["models"]["random_forest"])
        self.assertEqual(metrics.get("selected_model"), "random_forest")
        self.assertIn("split", metrics)
        self.assertEqual(metrics["split"]["strategy"], "temporal_by_appointment_date")

        pred_path = run.run_dir / "predictions" / "test_predictions.csv"
        self.assertTrue(pred_path.is_file())
        pred_text = pred_path.read_text(encoding="utf-8")
        self.assertIn("proba_baseline_logistic", pred_text)
        self.assertIn("proba_random_forest", pred_text)
        self.assertIn("y_true", pred_text)

        self.assertTrue((run.run_dir / "models" / "no_show_random_forest.joblib").is_file())
        self.assertTrue((run.run_dir / "models" / "no_show_logistic.joblib").is_file())
        self.assertTrue((run.run_dir / "report.md").is_file())
        self.assertIn("Random Forest", (run.run_dir / "report.md").read_text(encoding="utf-8"))

        # Legacy artifact compatibility (same out_dir contract as before).
        self.assertTrue((self.out_dir / "metrics.json").is_file())
        self.assertTrue((self.out_dir / "no_show_logistic.joblib").is_file())
        self.assertTrue((self.out_dir / "no_show_random_forest.joblib").is_file())
        self.assertTrue((self.out_dir / "no_show_test_predictions.csv").is_file())

        legacy = json.loads((self.out_dir / "metrics.json").read_text(encoding="utf-8"))
        self.assertAlmostEqual(
            legacy["metrics"]["random_forest"]["roc_auc"],
            summary["metrics"]["random_forest"]["roc_auc"],
        )
        self.assertAlmostEqual(
            legacy["metrics"]["baseline_logistic"]["roc_auc"],
            metrics["models"]["baseline_logistic"]["roc_auc"],
        )

    def test_controlled_failure_marks_run_failed(self) -> None:
        with patch(
            "scripts.train_no_show.run_training",
            side_effect=RuntimeError("simulated training failure"),
        ):
            with self.assertRaises(RuntimeError):
                run_no_show_pipeline(
                    db_path=DB_PATH,
                    out_dir=self.out_dir,
                    runs_dir=self.runs_dir,
                )

        run_dirs = [p for p in self.runs_dir.iterdir() if p.is_dir()]
        self.assertEqual(len(run_dirs), 1)
        meta = read_json(run_dirs[0] / "metadata.json")
        self.assertEqual(meta["status"], "failed")
        self.assertIn("simulated training failure", meta.get("error") or "")
        report = (run_dirs[0] / "report.md").read_text(encoding="utf-8")
        self.assertIn("failed", report)


if __name__ == "__main__":
    unittest.main()
