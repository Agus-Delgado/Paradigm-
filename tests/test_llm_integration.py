"""Tests de integración LLM — fallback, seguridad SQL y estructura de respuesta."""

from __future__ import annotations

import json
import os
import sys
import unittest
from dataclasses import fields
from pathlib import Path
from unittest.mock import patch

import pandas as pd

# Raíz del repo en path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.conversational.llm_logging import analyst_result_response_payload, estimate_tokens
from app.conversational.llm_security import reset_rate_limit, validate_llm_sql
from app.conversational.llm_service import (
    AnalystResult,
    analyst_result_to_dict,
    generate_insights,
    generate_sql_llm,
)
from app.conversational.nl_to_sql import _generate_sql_heuristic, generate_sql, generate_sql_llm_enhanced
from app.config.llm_config import LLMSettings


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "specialty_name": ["Cardio", "Derma", "Cardio"],
            "status_code": ["NO_SHOW", "ATTENDED", "ATTENDED"],
            "net_revenue": [100.0, 200.0, 150.0],
        }
    )


def _logical_types() -> dict[str, str]:
    return {
        "specialty_name": "categorical",
        "status_code": "categorical",
        "net_revenue": "numeric",
    }


class TestLLMSecurity(unittest.TestCase):
    def test_validate_rejects_dml(self) -> None:
        for sql in (
            "DELETE FROM data",
            "UPDATE data SET x=1",
            "DROP TABLE data",
            "SELECT 1; DELETE FROM data",
        ):
            ok, _ = validate_llm_sql(sql)
            self.assertFalse(ok, sql)

    def test_validate_accepts_select(self) -> None:
        ok, _ = validate_llm_sql("SELECT * FROM data LIMIT 10")
        self.assertTrue(ok)

    def test_validate_accepts_with(self) -> None:
        ok, _ = validate_llm_sql("WITH cte AS (SELECT 1) SELECT * FROM cte")
        self.assertTrue(ok)


class TestLLMFallback(unittest.TestCase):
    def setUp(self) -> None:
        reset_rate_limit()

    @patch.dict(os.environ, {"PARADIGM_LLM_PROVIDER": "disabled"}, clear=False)
    def test_generate_insights_fallback_when_disabled(self) -> None:
        from app.config import llm_config

        llm_config._DOTENV_LOADED = False
        df = _sample_df()
        result = generate_insights("test query", df, logical_types=_logical_types())
        self.assertFalse(result.used_llm)
        self.assertTrue(len(result.insight) > 10)
        self.assertTrue(len(result.recommendation) > 5)

    @patch.dict(os.environ, {"PARADIGM_LLM_PROVIDER": "disabled"}, clear=False)
    def test_generate_sql_matches_heuristic_when_disabled(self) -> None:
        from app.config import llm_config

        llm_config._DOTENV_LOADED = False
        df = _sample_df()
        lt = _logical_types()
        q = "comparar especialidad con ingreso"
        sql_pub, _ = generate_sql(q, df, lt, "healthcare_mart")
        sql_heu, _ = _generate_sql_heuristic(q, df, lt, "healthcare_mart")
        self.assertEqual(sql_pub, sql_heu)

        enhanced = generate_sql_llm_enhanced(q, df, lt, "healthcare_mart")
        self.assertEqual(enhanced.engine, "heuristic")
        self.assertFalse(enhanced.used_llm)
        ok, _ = validate_llm_sql(enhanced.sql)
        self.assertTrue(ok)

    @patch.dict(os.environ, {"PARADIGM_LLM_PROVIDER": "disabled"}, clear=False)
    def test_generate_sql_llm_module_fallback(self) -> None:
        from app.config import llm_config

        llm_config._DOTENV_LOADED = False
        df = _sample_df()
        lt = _logical_types()
        result = generate_sql_llm("comparar especialidad con ingreso", df, lt, "healthcare_mart")
        self.assertFalse(result.used_llm)
        ok, _ = validate_llm_sql(result.sql or "")
        self.assertTrue(ok)


class TestAnalystResultStructure(unittest.TestCase):
    def test_analyst_result_fields(self) -> None:
        names = {f.name for f in fields(AnalystResult)}
        required = {
            "sql",
            "insight",
            "recommendation",
            "business_impact",
            "confidence",
            "sources",
            "used_llm",
        }
        self.assertTrue(required.issubset(names))

    def test_analyst_result_to_dict_json_serializable(self) -> None:
        result = AnalystResult(
            sql="SELECT 1",
            insight="test",
            recommendation="act",
            business_impact="Medio",
            confidence="medium",
            sources=["a"],
            used_llm=True,
        )
        payload = analyst_result_to_dict(result)
        json.dumps(payload)
        log_payload = analyst_result_response_payload(result)
        self.assertEqual(log_payload["insight"], "test")
        self.assertEqual(log_payload["sql"], "SELECT 1")

    def test_estimate_tokens_positive(self) -> None:
        self.assertGreater(estimate_tokens("hello world" * 10), 0)


class TestRateLimit(unittest.TestCase):
    def setUp(self) -> None:
        reset_rate_limit()

    @patch.dict(os.environ, {"PARADIGM_LLM_PROVIDER": "disabled", "PARADIGM_LLM_RATE_LIMIT": "2"}, clear=False)
    def test_rate_limit_env_parsed(self) -> None:
        from app.conversational.llm_security import _max_requests_per_minute

        self.assertEqual(_max_requests_per_minute(), 2)


if __name__ == "__main__":
    unittest.main()
