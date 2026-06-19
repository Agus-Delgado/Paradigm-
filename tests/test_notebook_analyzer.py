"""Tests del analizador de notebooks (fallback heurístico)."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.conversational.notebook_analyzer import analyze_notebook
from app.conversational.notebook_parser import parse_notebook
from tests.test_notebook_parser import _analytical_notebook


class TestNotebookAnalyzer(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PARADIGM_LLM_PROVIDER"] = "disabled"

    def test_heuristic_analysis_structure(self) -> None:
        raw = json.dumps(_analytical_notebook())
        parsed, err = parse_notebook(raw, filename="presencialidad.ipynb")
        self.assertIsNone(err)
        assert parsed is not None

        with patch("app.conversational.notebook_analyzer.is_llm_available", return_value=False):
            result = analyze_notebook(parsed)

        self.assertFalse(result.used_llm)
        self.assertTrue(result.executive_summary)
        self.assertTrue(result.plain_language_summary)
        self.assertGreater(len(result.prioritized_recommendations), 0)
        self.assertGreater(len(result.critical_issues), 0)
        self.assertIn("presencialidad.ipynb", result.filename)

    def test_export_fields_present(self) -> None:
        from app.export_report import build_notebook_report_md

        raw = json.dumps(_analytical_notebook())
        parsed, _ = parse_notebook(raw, filename="presencialidad.ipynb")
        assert parsed is not None

        with patch("app.conversational.notebook_analyzer.is_llm_available", return_value=False):
            result = analyze_notebook(parsed)

        md = build_notebook_report_md(result, parsed)
        for section in (
            "## Resumen Ejecutivo",
            "## Aspectos Positivos",
            "## Áreas de Mejora",
            "## Issues Críticos",
            "## Recomendaciones Priorizadas",
            "## Sugerencias Técnicas Avanzadas",
            "## Resumen para no técnicos",
        ):
            self.assertIn(section, md)


if __name__ == "__main__":
    unittest.main()
