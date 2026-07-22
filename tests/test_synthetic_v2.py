"""Tests del generador sintético v2 (incl. calibración)."""

from __future__ import annotations

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

import numpy as np  # noqa: E402
from paradigm.synthetic_v2 import (  # noqa: E402
    POST_OUTCOME_COLUMNS,
    PREDECISIONAL_COLUMNS,
    TRUTH_COLUMNS,
    CalibrationError,
    ScenarioId,
    calibrate_beta0_bisection,
    config_for_scenario,
    fingerprint_frames,
    generate_dataset,
    run_generation,
)
from paradigm.synthetic_v2.generate import (  # noqa: E402
    _sample_skeletons,
    sample_patients,
    sample_providers,
)
from scripts.generate_synthetic_v2 import main as cli_main  # noqa: E402


def _small_cfg(scenario: str, seed: int = 42, **kw):
    return config_for_scenario(
        scenario,
        seed=seed,
        n_appointments=kw.pop("n_appointments", 500),
        n_patients=kw.pop("n_patients", 80),
        **kw,
    )


class TestSyntheticV2Reproducibility(unittest.TestCase):
    def test_same_seed_same_hashes(self) -> None:
        cfg = _small_cfg("signal_moderate", seed=42)
        a = generate_dataset(cfg)
        b = generate_dataset(cfg)
        fa = fingerprint_frames(a["frames"])
        fb = fingerprint_frames(b["frames"])
        self.assertEqual(fa, fb)
        self.assertEqual(a["beta_0_used"], b["beta_0_used"])

    def test_different_seed_different_data(self) -> None:
        a = fingerprint_frames(generate_dataset(_small_cfg("signal_moderate", seed=42))["frames"])
        b = fingerprint_frames(generate_dataset(_small_cfg("signal_moderate", seed=99))["frames"])
        self.assertNotEqual(a["fact_appointment"], b["fact_appointment"])


class TestSyntheticV2Calibration(unittest.TestCase):
    def _skeletons(self, cfg):
        rng = np.random.default_rng(cfg.seed)
        patients = sample_patients(rng, cfg)
        providers = sample_providers(rng, cfg)
        skeletons = _sample_skeletons(rng, cfg, patients, providers)
        return sorted(
            skeletons,
            key=lambda r: (r["appointment_date"], r["appointment_start"], r["appointment_id"]),
        )

    def test_solver_converges_and_expected_within_tol(self) -> None:
        cfg = _small_cfg("signal_moderate", seed=42, n_appointments=400)
        sk = self._skeletons(cfg)
        result = calibrate_beta0_bisection(sk, cfg)
        self.assertTrue(result.converged)
        self.assertLessEqual(result.expected_abs_error, cfg.calibration_tolerance)
        self.assertAlmostEqual(result.expected_rate, cfg.target_no_show_rate, delta=cfg.calibration_tolerance)

    def test_intercept_reproducible(self) -> None:
        cfg = _small_cfg("signal_strong", seed=7, n_appointments=350)
        sk = self._skeletons(cfg)
        a = calibrate_beta0_bisection(sk, cfg)
        b = calibrate_beta0_bisection(sk, cfg)
        self.assertEqual(a.beta_0, b.beta_0)
        self.assertEqual(a.iterations, b.iterations)

    def test_controlled_nonconvergence(self) -> None:
        cfg = _small_cfg(
            "signal_moderate",
            seed=42,
            n_appointments=200,
            target_no_show_rate=0.99,
            p_clip_high=0.85,
            calibration_max_iterations=5,
            calibration_tolerance=1e-8,
        )
        sk = self._skeletons(cfg)
        with self.assertRaises(CalibrationError):
            calibrate_beta0_bisection(sk, cfg)

    def test_comparable_prevalence_across_scenarios(self) -> None:
        rates = []
        for scenario in ("signal_weak", "signal_moderate", "signal_strong"):
            gen = generate_dataset(_small_cfg(scenario, seed=42, n_appointments=900))
            fact = gen["frames"]["fact_appointment"]
            elig = fact[fact["status_code"].isin(["ATTENDED", "NO_SHOW"])]
            rates.append(float((elig["status_code"] == "NO_SHOW").mean()))
            self.assertTrue(gen["calibration"].converged)
            self.assertLessEqual(
                gen["calibration"].expected_abs_error,
                gen["config_used"].calibration_tolerance,
            )
        self.assertLess(max(rates) - min(rates), 0.06, msg=f"rates={rates}")

    def test_calibration_metrics_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _small_cfg(
                "signal_moderate",
                seed=11,
                dataset_id="cal_persist",
                output_root=tmp,
                n_appointments=400,
            )
            result = run_generation(cfg, output_root=Path(tmp))
            truth = json.loads(
                (result.output_dir / "generator_truth.json").read_text(encoding="utf-8")
            )
            metrics = json.loads(
                (result.output_dir / "validation_metrics.json").read_text(encoding="utf-8")
            )
            cal = truth["calibration"]
            for key in (
                "calibrated_intercept",
                "expected_rate",
                "observed_rate",
                "expected_abs_error",
                "iterations",
                "converged",
            ):
                self.assertIn(key, cal, msg=key)
            self.assertTrue(cal["converged"])
            self.assertTrue(metrics["calibration_converged"])
            self.assertTrue(metrics["expected_rate_ok"])
            self.assertIsNotNone(metrics["calibrated_intercept"])
            self.assertTrue(result.validation.checks_passed)


class TestSyntheticV2SignalOrdering(unittest.TestCase):
    def test_auc_increases_weak_moderate_strong(self) -> None:
        aucs = []
        rates = []
        for scenario in ("signal_weak", "signal_moderate", "signal_strong"):
            with tempfile.TemporaryDirectory() as tmp:
                cfg = _small_cfg(
                    scenario,
                    seed=42,
                    n_appointments=1200,
                    dataset_id=scenario,
                    output_root=tmp,
                )
                result = run_generation(cfg, output_root=Path(tmp))
                self.assertTrue(result.validation.checks_passed)
                self.assertIsNotNone(result.validation.true_p_auc)
                aucs.append(result.validation.true_p_auc)
                rates.append(result.validation.noshow_rate)
        self.assertLess(aucs[0], aucs[1], msg=f"weak vs moderate: {aucs}")
        self.assertLess(aucs[1], aucs[2], msg=f"moderate vs strong: {aucs}")
        self.assertLess(max(rates) - min(rates), 0.06, msg=f"rates={rates}")


class TestSyntheticV2ProbabilityAndSeparation(unittest.TestCase):
    def test_probabilities_valid(self) -> None:
        frames = generate_dataset(_small_cfg("signal_moderate"))["frames"]
        p = frames["fact_appointment"]["true_no_show_probability"]
        self.assertTrue(((p > 0.0) & (p < 1.0)).all())
        self.assertGreaterEqual(p.min(), 0.02 - 1e-9)
        self.assertLessEqual(p.max(), 0.85 + 1e-9)

    def test_pre_post_separation(self) -> None:
        overlap = set(PREDECISIONAL_COLUMNS) & set(POST_OUTCOME_COLUMNS)
        self.assertEqual(overlap, set())
        frames = generate_dataset(_small_cfg("signal_moderate"))["frames"]
        fact_cols = set(frames["fact_appointment"].columns)
        for col in TRUTH_COLUMNS:
            self.assertIn(col, fact_cols)
        for col in ("appointment_status_id", "cancellation_ts"):
            self.assertIn(col, fact_cols)
        self.assertNotIn("line_amount", fact_cols)
        self.assertIn("line_amount", frames["fact_billing_line"].columns)


class TestSyntheticV2Persistence(unittest.TestCase):
    def test_config_and_truth_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _small_cfg(
                "signal_moderate",
                seed=7,
                dataset_id="persist_test",
                output_root=tmp,
            )
            result = run_generation(cfg, output_root=Path(tmp))
            out = result.output_dir
            for name in (
                "generator_config.json",
                "generator_truth.json",
                "generation_metadata.json",
                "validation_metrics.json",
                "fact_appointment.csv",
                "dim_patient.csv",
                "appointment_truth.csv",
            ):
                self.assertTrue((out / name).is_file(), msg=name)
            config_json = json.loads((out / "generator_config.json").read_text(encoding="utf-8"))
            truth_json = json.loads((out / "generator_truth.json").read_text(encoding="utf-8"))
            self.assertEqual(config_json["seed"], 7)
            self.assertEqual(config_json["target_no_show_rate"], 0.13)
            self.assertEqual(truth_json["seed"], 7)
            self.assertTrue(result.validation.checks_passed)


class TestSyntheticV2CLI(unittest.TestCase):
    def test_cli_temp_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code = cli_main(
                [
                    "--scenario",
                    "signal_weak",
                    "--seed",
                    "3",
                    "--output-dir",
                    tmp,
                    "--dataset-id",
                    "cli_run",
                    "--n-appointments",
                    "300",
                    "--n-patients",
                    "60",
                ]
            )
            self.assertEqual(code, 0)
            out = Path(tmp) / "cli_run"
            self.assertTrue((out / "generator_config.json").is_file())
            self.assertTrue((out / "validation_metrics.json").is_file())


class TestSyntheticV2ContractsImport(unittest.TestCase):
    def test_scenario_enum_and_default(self) -> None:
        cfg = config_for_scenario(ScenarioId.SIGNAL_MODERATE)
        self.assertEqual(cfg.signal_scale, 1.0)
        self.assertEqual(cfg.target_no_show_rate, 0.13)
        self.assertEqual(cfg.noise.sigma_eps, 0.35)


if __name__ == "__main__":
    unittest.main()
