"""Tests de segmentación y drift (reproducibilidad, estabilidad, leakage)."""

from __future__ import annotations

import sys
import tempfile
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

from paradigm.ml_v2.features import FORBIDDEN_FEATURE_COLUMNS  # noqa: E402
from paradigm.monitoring.clustering import (  # noqa: E402
    compare_k,
    fit_kmeans_pipeline,
    stability_ari,
)
from paradigm.monitoring.drift import (  # noqa: E402
    drift_report_between_windows,
    prevalence_drift,
)
from paradigm.monitoring.features import build_clustering_frame  # noqa: E402
from paradigm.monitoring.pipeline import run_segmentation_and_drift  # noqa: E402

DATA = ROOT / "data" / "synthetic_v2" / "signal_moderate_seed42" / "fact_appointment.csv"
HAS_DATA = DATA.is_file()


def _toy(n: int = 200, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # Dos blobs por lead_time / channel
    channel = rng.choice([1, 2, 3], size=n, p=[0.5, 0.3, 0.2])
    lead = np.where(channel == 1, rng.normal(20, 3, n), rng.normal(5, 2, n))
    lead = np.clip(lead, 0, None)
    return pd.DataFrame(
        {
            "appointment_id": [f"A{i}" for i in range(n)],
            "appointment_date": pd.date_range("2024-01-01", periods=n, freq="D"),
            "provider_id": rng.integers(1, 5, n),
            "specialty_id": rng.integers(1, 4, n),
            "booking_channel_id": channel,
            "coverage_id": rng.integers(1, 3, n),
            "age_band": rng.choice(["18-34", "35-49", "50-64"], n),
            "sex": rng.choice(["F", "M"], n),
            "lead_time_days": lead,
            "appointment_hour": rng.integers(8, 18, n),
            "appointment_dow": rng.integers(0, 7, n),
            "appointment_month": rng.integers(1, 13, n),
            "booking_hour": rng.integers(8, 18, n),
            "reminder_sent": rng.integers(0, 2, n),
            "is_repeat_patient": rng.integers(0, 2, n),
            "patient_prior_appt_count": rng.integers(0, 10, n),
            "patient_prior_no_show_count": rng.integers(0, 3, n),
            "patient_prior_no_show_rate": rng.random(n),
            "provider_prior_appt_count": rng.integers(0, 50, n),
            "provider_prior_no_show_count": rng.integers(0, 10, n),
            "provider_prior_no_show_rate": rng.random(n),
            "target_no_show": rng.integers(0, 2, n),
            "true_no_show_probability": rng.random(n),
        }
    )


class TestLeakage(unittest.TestCase):
    def test_clustering_frame_excludes_truth(self) -> None:
        df = _toy(50)
        x = build_clustering_frame(df)
        self.assertNotIn("true_no_show_probability", x.columns)
        self.assertNotIn("target_no_show", x.columns)
        overlap = set(x.columns) & set(FORBIDDEN_FEATURE_COLUMNS)
        self.assertEqual(overlap, set())


class TestReproducibility(unittest.TestCase):
    def test_same_seed_same_labels(self) -> None:
        df = _toy(120, seed=1)
        _, a = fit_kmeans_pipeline(df, n_clusters=3, seed=7)
        _, b = fit_kmeans_pipeline(df, n_clusters=3, seed=7)
        np.testing.assert_array_equal(a, b)

    def test_pipeline_reproducible(self) -> None:
        df = _toy(150, seed=2)
        r1 = run_segmentation_and_drift(df, k_values=(2, 3), n_windows=3, seed=42)
        r2 = run_segmentation_and_drift(df, k_values=(2, 3), n_windows=3, seed=42)
        self.assertEqual(r1["best_k"], r2["best_k"])
        self.assertEqual(r1["labels"], r2["labels"])
        self.assertAlmostEqual(
            r1["stability"]["mean_seed_ari"],
            r2["stability"]["mean_seed_ari"],
            places=10,
        )


class TestStability(unittest.TestCase):
    def test_stability_ari_high_on_separated_blobs(self) -> None:
        df = _toy(240, seed=0)
        stab = stability_ari(df, n_clusters=2, seeds=(0, 1, 2))
        self.assertGreaterEqual(stab["mean_seed_ari"], 0.5)
        rows = compare_k(df, k_values=(2, 3), seed=0)
        self.assertTrue(any(r["k"] == 2 for r in rows))
        self.assertIn("silhouette", rows[0])


class TestDrift(unittest.TestCase):
    def test_prevalence_and_feature_drift(self) -> None:
        ref = _toy(100, seed=0)
        cur = ref.copy()
        cur["lead_time_days"] = cur["lead_time_days"] + 15
        cur["target_no_show"] = 1
        prev = prevalence_drift(ref["target_no_show"], cur["target_no_show"])
        self.assertGreater(prev["abs_diff"], 0.2)
        report = drift_report_between_windows(ref, cur)
        lead = next(r for r in report["numeric"] if r["feature"] == "lead_time_days")
        self.assertGreater(lead["psi"], 0.1)
        self.assertIn("lead_time_days", report["alerts"] + [lead["feature"]])


@unittest.skipUnless(HAS_DATA, "synthetic_v2 dataset missing")
class TestRealRun(unittest.TestCase):
    def test_script_registers_experiment(self) -> None:
        from scripts.run_segmentation_drift import main

        with tempfile.TemporaryDirectory() as tmp:
            code = main(
                [
                    "--dataset-id",
                    "signal_moderate_seed42",
                    "--runs-dir",
                    tmp,
                    "--json-out",
                    str(Path(tmp) / "out.json"),
                    "--k-max",
                    "4",
                    "--n-windows",
                    "3",
                ]
            )
            self.assertEqual(code, 0)
            self.assertTrue((Path(tmp) / "out.json").is_file())


if __name__ == "__main__":
    unittest.main()
