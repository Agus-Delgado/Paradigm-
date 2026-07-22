"""Tests de intervención sintética (policy_intervention)."""

from __future__ import annotations

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

from paradigm.ml_v2.features import (  # noqa: E402
    FORBIDDEN_FEATURE_COLUMNS,
    PREDECISIONAL_CATEGORICAL,
    PREDECISIONAL_NUMERIC,
    assert_no_leakage,
)
from paradigm.synthetic_v2 import (  # noqa: E402
    PREDECISIONAL_COLUMNS,
    ScenarioId,
    config_for_scenario,
    fingerprint_frames,
    generate_dataset,
    run_generation,
)
from paradigm.synthetic_v2.intervention import (  # noqa: E402
    INTERVENTION_ASSIGNMENT_COLUMNS,
    INTERVENTION_TRUTH_COLUMNS,
    treatment_logit_delta,
)


class TestInterventionGeneration(unittest.TestCase):
    def test_reproducibility_same_seed(self) -> None:
        cfg = config_for_scenario(
            ScenarioId.POLICY_INTERVENTION,
            seed=7,
            n_appointments=400,
            n_patients=80,
        )
        a = fingerprint_frames(generate_dataset(cfg)["frames"])
        b = fingerprint_frames(generate_dataset(cfg)["frames"])
        self.assertEqual(a, b)

    def test_treatment_balance_and_negative_ate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = config_for_scenario(
                ScenarioId.POLICY_INTERVENTION,
                seed=42,
                n_appointments=800,
                n_patients=100,
                dataset_id="interv_test",
                output_root=tmp,
            )
            result = run_generation(cfg, output_root=Path(tmp))
            self.assertTrue(result.validation.checks_passed)
            self.assertTrue(result.validation.intervention_enabled)
            self.assertIsNotNone(result.validation.treatment_rate)
            assert result.validation.treatment_rate is not None
            self.assertGreater(result.validation.treatment_rate, 0.25)
            self.assertLess(result.validation.treatment_rate, 0.75)
            self.assertIsNotNone(result.validation.ate_probability)
            assert result.validation.ate_probability is not None
            self.assertLess(result.validation.ate_probability, 0.0)
            self.assertTrue(result.validation.intervention_balance_ok)

    def test_heterogeneous_effects_by_segment(self) -> None:
        # WEB + lead largo debe tener delta más negativo que reception + lead corto
        from paradigm.synthetic_v2.intervention import InterventionParams

        p = InterventionParams(enabled=True)
        d_web_long = treatment_logit_delta(
            lead_time_days=20,
            channel_id=1,
            appointment_hour=16,
            is_repeat_patient=0,
            params=p,
        )
        d_rec_short = treatment_logit_delta(
            lead_time_days=2,
            channel_id=3,
            appointment_hour=10,
            is_repeat_patient=1,
            params=p,
        )
        self.assertLess(d_web_long, d_rec_short)

    def test_no_leakage_into_risk_features(self) -> None:
        overlap = set(PREDECISIONAL_COLUMNS) & (
            set(INTERVENTION_TRUTH_COLUMNS) | set(INTERVENTION_ASSIGNMENT_COLUMNS)
        )
        self.assertEqual(overlap, set())
        risk_cols = PREDECISIONAL_CATEGORICAL + PREDECISIONAL_NUMERIC
        assert_no_leakage(risk_cols)
        for col in list(INTERVENTION_TRUTH_COLUMNS) + list(INTERVENTION_ASSIGNMENT_COLUMNS):
            self.assertIn(col, FORBIDDEN_FEATURE_COLUMNS)

    def test_potential_outcomes_persisted(self) -> None:
        cfg = config_for_scenario(
            ScenarioId.POLICY_INTERVENTION,
            seed=3,
            n_appointments=300,
            n_patients=60,
        )
        fact = generate_dataset(cfg)["frames"]["fact_appointment"]
        for col in (
            "extra_reminder",
            "intervention_cost",
            "true_p0",
            "true_p1",
            "true_ite_probability",
            "true_y0",
            "true_y1",
            "true_ite",
        ):
            self.assertIn(col, fact.columns)
        elig = fact[fact["status_code"].isin(["ATTENDED", "NO_SHOW"])]
        # Cost only when treated
        treated = elig[elig["extra_reminder"] == 1]
        if len(treated):
            self.assertTrue((treated["intervention_cost"] > 0).all())
        control = elig[elig["extra_reminder"] == 0]
        if len(control):
            self.assertTrue((control["intervention_cost"] == 0).all())


if __name__ == "__main__":
    unittest.main()
