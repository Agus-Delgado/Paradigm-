"""Tests básicos del Evaluation Framework conversacional."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.conversational.evaluation.evaluator import ConversationalEvaluator, EvaluationSample
from app.conversational.evaluation.leaderboard import (
    average_of_averages,
    build_leaderboard,
    leaderboard_dataframe,
)
from app.conversational.evaluation.metrics import (
    faithfulness_score,
    semantic_similarity_simple,
    sql_validity,
)


class TestEvaluationMetrics(unittest.TestCase):
    def test_sql_validity_accepts_select(self) -> None:
        score = sql_validity("SELECT * FROM data LIMIT 5")
        self.assertEqual(score, 1.0)

    def test_sql_validity_rejects_mutation(self) -> None:
        score = sql_validity("UPDATE data SET status_code='ATTENDED'")
        self.assertEqual(score, 0.0)

    def test_semantic_similarity_simple(self) -> None:
        similar = semantic_similarity_simple(
            "Cardiologia concentra mayor no-show",
            "La especialidad con mayor no-show es cardiologia",
        )
        dissimilar = semantic_similarity_simple(
            "Forecast de demanda mensual",
            "La especialidad con mayor no-show es cardiologia",
        )
        assert similar is not None
        assert dissimilar is not None
        self.assertGreater(similar, dissimilar)
        self.assertGreaterEqual(similar, 0.0)
        self.assertLessEqual(similar, 1.0)

    def test_faithfulness_score(self) -> None:
        faithful = faithfulness_score(
            "Cardiologia presenta mayor no-show",
            "Reporte no-show por especialidad: cardiologia tiene el valor mas alto",
        )
        weak = faithfulness_score(
            "Forecast LSTM para demanda",
            "Reporte no-show por especialidad: cardiologia tiene el valor mas alto",
        )
        assert faithful is not None
        assert weak is not None
        self.assertGreater(faithful, weak)
        self.assertGreaterEqual(faithful, 0.0)
        self.assertLessEqual(faithful, 1.0)


class TestConversationalEvaluator(unittest.TestCase):
    def _mock_samples(self) -> list[EvaluationSample]:
        return [
            EvaluationSample(
                sample_id="s1",
                query="Top no-show specialty",
                response_text="Cardiologia tiene el mayor no-show",
                response_sql=(
                    "SELECT specialty_name, COUNT(*) AS n FROM data "
                    "WHERE status_code='NO_SHOW' GROUP BY specialty_name ORDER BY n DESC LIMIT 1"
                ),
                expected_text="La especialidad con mayor no-show es cardiologia",
                expected_sql=(
                    "SELECT specialty_name, COUNT(*) AS n FROM data "
                    "WHERE status_code='NO_SHOW' GROUP BY specialty_name ORDER BY n DESC LIMIT 1"
                ),
                evidence_text="No-show por especialidad en la tabla consolidada",
            ),
            EvaluationSample(
                sample_id="s2",
                query="Can you update rows?",
                response_text="No se permiten cambios de escritura",
                response_sql="UPDATE data SET status_code='ATTENDED'",
                expected_text="Solo lectura",
                expected_sql="SELECT status_code, COUNT(*) FROM data GROUP BY status_code",
                evidence_text="Politica: solo SELECT o WITH",
            ),
        ]

    def test_evaluate_run_with_mock_samples(self) -> None:
        evaluator = ConversationalEvaluator()
        run = evaluator.evaluate_run(self._mock_samples(), run_id="unit_eval_run")

        self.assertEqual(run.run_id, "unit_eval_run")
        self.assertEqual(run.n_samples, 2)
        self.assertEqual(len(run.sample_results), 2)
        self.assertIn("sql_validity", run.average_metrics)
        self.assertGreaterEqual(run.overall_score, 0.0)
        self.assertLessEqual(run.overall_score, 1.0)

    def test_save_run_to_directory(self) -> None:
        evaluator = ConversationalEvaluator()
        run = evaluator.evaluate_run(self._mock_samples(), run_id="unit_eval_saved")

        with tempfile.TemporaryDirectory() as tmp_dir:
            out = evaluator.save_run(run, output_dir=Path(tmp_dir))
            self.assertTrue(out.is_file())
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["run_id"], "unit_eval_saved")
            self.assertEqual(payload["n_samples"], 2)

    def test_samples_from_chat_history(self) -> None:
        chat = [
            {
                "query": "Top no-show",
                "payload": {
                    "insight": "Cardiologia lidera no-show",
                    "sql": "SELECT specialty_name FROM data LIMIT 1",
                    "used_llm": True,
                    "confidence": "medium",
                },
            }
        ]

        samples = ConversationalEvaluator.samples_from_chat_history(chat, run_label="chat_unit")
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].sample_id, "chat_unit_turn_1")
        self.assertIn("turn_index", samples[0].metadata)


class TestLeaderboard(unittest.TestCase):
    def test_build_leaderboard_and_aggregates(self) -> None:
        evaluator = ConversationalEvaluator()

        samples_good = [
            EvaluationSample(
                sample_id="good_1",
                query="Q1",
                response_text="Respuesta correcta",
                expected_text="Respuesta correcta",
                response_sql="SELECT 1",
                expected_sql="SELECT 1",
                evidence_text="Respuesta correcta",
            )
        ]
        samples_bad = [
            EvaluationSample(
                sample_id="bad_1",
                query="Q2",
                response_text="Sin relacion",
                expected_text="Respuesta correcta",
                response_sql="UPDATE data SET x=1",
                expected_sql="SELECT 1",
                evidence_text="Respuesta correcta",
            )
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir)
            evaluator.evaluate_and_save(samples_good, run_id="run_good", output_dir=out_dir)
            evaluator.evaluate_and_save(samples_bad, run_id="run_bad", output_dir=out_dir)

            leaderboard = build_leaderboard(eval_dir=out_dir)
            self.assertEqual(len(leaderboard), 2)
            self.assertEqual(leaderboard[0].run_id, "run_good")

            df = leaderboard_dataframe(eval_dir=out_dir)
            self.assertEqual(len(df), 2)
            self.assertIn("overall_score", df.columns)

            avg = average_of_averages(eval_dir=out_dir)
            self.assertIn("overall_score", avg)
            self.assertGreaterEqual(avg["overall_score"], 0.0)
            self.assertLessEqual(avg["overall_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
