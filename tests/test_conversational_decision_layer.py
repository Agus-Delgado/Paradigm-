"""Tests de la capa conversacional Decide (prescriptive)."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "python" / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app.conversational.decision_layer import (  # noqa: E402
    FORBIDDEN_CAUSAL_PATTERNS,
    answer_cost_sensitivity,
    answer_decision_query,
    answer_which_policy,
    answer_who_to_contact,
    answer_why_priority,
    classify_decision_intent,
    decision_answer_to_analyst_fields,
)
from app.conversational.llm_service import generate_insights  # noqa: E402
from paradigm.prescriptive import PrescriptiveConfig, run_prescriptive_engine  # noqa: E402

PRED = (
    ROOT
    / "ml"
    / "experiments"
    / "runs"
    / "20260721_230255_no_show_v2_signal_moderate_seed42"
    / "predictions"
    / "test_predictions.csv"
)
HAS_PRED = PRED.is_file()


def _preds() -> pd.DataFrame:
    return pd.read_csv(PRED)


@unittest.skipUnless(HAS_PRED, "moderate predictions missing")
class TestDecisionIntents(unittest.TestCase):
    def test_classify_four_queries(self) -> None:
        self.assertEqual(
            classify_decision_intent("¿A quiénes debería contactar hoy?"),
            "who_to_contact",
        )
        self.assertEqual(
            classify_decision_intent("¿Por qué esta cita APT-01226 tiene prioridad?"),
            "why_priority",
        )
        self.assertEqual(
            classify_decision_intent("¿Qué política se está usando?"),
            "which_policy",
        )
        self.assertEqual(
            classify_decision_intent("¿Qué cambia si aumenta el costo?"),
            "cost_sensitivity",
        )
        self.assertEqual(classify_decision_intent("resumen de ventas"), "not_decision")

    def test_ranking_who_to_contact(self) -> None:
        result = run_prescriptive_engine(_preds(), PrescriptiveConfig())
        ans = answer_who_to_contact(result, top_n=5)
        self.assertEqual(ans.intent, "who_to_contact")
        self.assertIn("[RECOMENDACIÓN]", ans.insight)
        self.assertIn("[PREDICCIÓN]", ans.insight)
        self.assertIn("capacidad", ans.insight.lower())
        self.assertTrue(ans.evidence["top_ids"])

    def test_explain_appointment(self) -> None:
        result = run_prescriptive_engine(_preds(), PrescriptiveConfig())
        top_id = result.recommendations.iloc[0]["appointment_id"]
        ans = answer_why_priority(result, appointment_id=str(top_id))
        self.assertEqual(ans.intent, "why_priority")
        self.assertIn(str(top_id), ans.insight)
        self.assertIn("risk_score", ans.evidence["row"])

    def test_policy_query(self) -> None:
        result = run_prescriptive_engine(_preds(), PrescriptiveConfig())
        ans = answer_which_policy(result)
        self.assertEqual(ans.intent, "which_policy")
        self.assertEqual(ans.evidence["policy_used"], result.policy_used)
        self.assertIn(result.policy_used, ans.insight)

    def test_cost_sensitivity(self) -> None:
        ans = answer_cost_sensitivity(_preds(), PrescriptiveConfig())
        self.assertEqual(ans.intent, "cost_sensitivity")
        self.assertIn("[SIMULACIÓN]", ans.insight)
        policies = {r["policy"] for r in ans.evidence["scenarios"]}
        self.assertTrue(policies)
        # Con costo muy alto debería aparecer none
        self.assertIn("none", policies)

    def test_no_false_causality(self) -> None:
        ans = answer_decision_query(
            "¿A quiénes debería contactar hoy?",
            predictions=_preds(),
        )
        assert ans is not None
        blob = (ans.insight + ans.recommendation + ans.explanation).lower()
        for pat in FORBIDDEN_CAUSAL_PATTERNS:
            self.assertIsNone(re.search(pat, blob), msg=pat)

    def test_fallback_without_llm(self) -> None:
        with patch.dict(os.environ, {"PARADIGM_LLM_PROVIDER": "disabled"}, clear=False):
            from app.config import llm_config

            llm_config._DOTENV_LOADED = False
            result = generate_insights(
                "¿Qué política se está usando?",
                context_df=None,
            )
            self.assertFalse(result.used_llm)
            self.assertIn("decision_intent:which_policy", result.sources)
            self.assertIn("prescriptive:engine", result.sources)
            self.assertIn("[DATO]", result.insight)

    def test_analyst_mapping_includes_evidence(self) -> None:
        ans = answer_decision_query(
            "¿A quiénes debería contactar hoy?",
            predictions=_preds(),
        )
        assert ans is not None
        fields = decision_answer_to_analyst_fields(ans)
        self.assertIn("Evidencia", fields["explanation"])
        payload = json.loads(fields["raw_response"])
        self.assertEqual(payload["intent"], "who_to_contact")


if __name__ == "__main__":
    unittest.main()
