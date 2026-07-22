"""Tests de calibración y segmentación del análisis de error v2."""

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

from paradigm.ml_v2.error_analysis import (  # noqa: E402
    build_analysis_frame,
    calibration_curve_points,
    calibration_slope_intercept,
    confusion_counts,
    risk_decile_metrics,
    segment_error_table,
)


class TestCalibrationMetrics(unittest.TestCase):
    def test_perfect_scores_near_identity_slope(self) -> None:
        rng = np.random.default_rng(0)
        p = rng.uniform(0.05, 0.95, size=2000)
        y = (rng.random(2000) < p).astype(int)
        cal = calibration_slope_intercept(y, p)
        self.assertIsNotNone(cal["slope"])
        self.assertIsNotNone(cal["intercept"])
        assert cal["slope"] is not None
        assert cal["intercept"] is not None
        self.assertAlmostEqual(cal["slope"], 1.0, delta=0.25)
        self.assertAlmostEqual(cal["intercept"], 0.0, delta=0.35)

    def test_calibration_curve_has_bins(self) -> None:
        y = np.array([0, 0, 0, 1, 1, 1, 0, 1, 0, 1] * 20)
        p = np.linspace(0.05, 0.95, len(y))
        curve = calibration_curve_points(y, p, n_bins=5)
        self.assertEqual(len(curve["mean_predicted"]), len(curve["fraction_positives"]))
        self.assertGreaterEqual(len(curve["mean_predicted"]), 2)

    def test_risk_deciles_cover_all_rows(self) -> None:
        y = np.array([0, 1] * 50)
        p = np.linspace(0.01, 0.99, 100)
        rows = risk_decile_metrics(y, p, n_deciles=10)
        self.assertEqual(sum(r["n"] for r in rows), 100)
        self.assertEqual(rows[0]["decile"], 1)
        self.assertEqual(rows[-1]["decile"], 10)
        self.assertLessEqual(rows[0]["mean_predicted"], rows[-1]["mean_predicted"])


class TestSegmentation(unittest.TestCase):
    def test_segment_error_table_and_confusion(self) -> None:
        frame = pd.DataFrame(
            {
                "y_true": [0, 0, 1, 1, 0, 1],
                "proba": [0.1, 0.8, 0.2, 0.9, 0.4, 0.7],
                "channel": ["WEB", "WEB", "PHONE", "PHONE", "WEB", "PHONE"],
            }
        )
        rows = segment_error_table(frame, proba_col="proba", segment_col="channel")
        self.assertEqual({r["segment"] for r in rows}, {"WEB", "PHONE"})
        for r in rows:
            self.assertIn("fp", r)
            self.assertIn("fn", r)
            self.assertEqual(r["fp"] + r["fn"] + (r["n"] - r["fp"] - r["fn"]), r["n"])
        conf = confusion_counts(frame["y_true"], frame["proba"], threshold=0.5)
        self.assertEqual(conf["tp"] + conf["fp"] + conf["tn"] + conf["fn"], 6)

    def test_build_analysis_frame_joins_segments(self) -> None:
        preds = pd.DataFrame(
            {
                "appointment_id": ["A1", "A2"],
                "y_true": [0, 1],
                "proba_baseline_logistic": [0.2, 0.8],
                "proba_random_forest": [0.3, 0.7],
            }
        )
        appts = pd.DataFrame(
            {
                "appointment_id": ["A1", "A2"],
                "lead_time_days": [2, 20],
                "booking_channel_id": [1, 2],
                "appointment_hour": [9, 16],
                "specialty_id": [1, 2],
                "is_repeat_patient": [0, 1],
            }
        )
        frame = build_analysis_frame(preds, appts)
        self.assertEqual(list(frame["lead_bin"]), ["0-3", "15-30"])
        self.assertEqual(list(frame["channel"]), ["WEB", "PHONE"])
        self.assertEqual(list(frame["hour_bin"]), ["8-11", "15-17"])
        self.assertEqual(list(frame["recurrence"]), ["first", "repeat"])


if __name__ == "__main__":
    unittest.main()
