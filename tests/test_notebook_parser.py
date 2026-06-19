"""Tests del parser de notebooks Jupyter (.ipynb)."""

from __future__ import annotations

import json
import sys
import unittest
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.conversational.notebook_parser import (
    build_llm_context,
    extract_headings,
    parse_notebook,
)


def _minimal_notebook() -> dict:
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": "# Intro\n\nTexto introductorio.",
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [
                    {
                        "output_type": "stream",
                        "name": "stdout",
                        "text": "hello\n",
                    }
                ],
                "source": "print('hello')",
            },
        ],
    }


def _analytical_notebook() -> dict:
    """Fixture tipo notebook analítico (presencialidad / KPIs)."""
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {"title": "Análisis de Presencialidad"},
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": (
                    "# Análisis de Presencialidad\n\n"
                    "## Objetivo\n\n"
                    "Medir tasa de asistencia por sede y especialidad."
                ),
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 1,
                "outputs": [
                    {
                        "output_type": "execute_result",
                        "metadata": {},
                        "data": {
                            "text/plain": "   sede  tasa_asistencia\n0  Norte              0.82\n1  Sur                0.71"
                        },
                        "execution_count": 1,
                    }
                ],
                "source": (
                    "import pandas as pd\n"
                    "df = pd.read_csv('asistencia.csv')\n"
                    "df.groupby('sede')['asistio'].mean()"
                ),
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 2,
                "outputs": [
                    {
                        "output_type": "display_data",
                        "metadata": {},
                        "data": {
                            "text/plain": "<Figure size 640x480 with 1 Axes>",
                            "image/png": "iVBORw0KGgo=",
                        },
                    }
                ],
                "source": "import matplotlib.pyplot as plt\nplt.bar(df['sede'], df['tasa'])",
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": "## Conclusiones\n\nLa sede Sur requiere seguimiento.",
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": 3,
                "outputs": [
                    {
                        "output_type": "error",
                        "ename": "KeyError",
                        "evalue": "'columna_inexistente'",
                        "traceback": [],
                    }
                ],
                "source": "df['columna_inexistente']",
            },
        ],
    }


class TestNotebookParser(unittest.TestCase):
    def test_parse_minimal_notebook(self) -> None:
        raw = json.dumps(_minimal_notebook())
        parsed, err = parse_notebook(raw, filename="demo.ipynb")

        self.assertIsNone(err)
        assert parsed is not None
        self.assertEqual(parsed.filename, "demo.ipynb")
        self.assertEqual(parsed.title, "Intro")
        self.assertEqual(parsed.cell_count, 2)
        self.assertEqual(parsed.n_markdown, 1)
        self.assertEqual(parsed.n_code, 1)
        self.assertEqual(parsed.n_with_output, 1)

        code_cell = parsed.cells[1]
        self.assertEqual(code_cell.cell_type, "code")
        self.assertEqual(code_cell.execution_count, 1)
        self.assertIn("hello", code_cell.outputs_summary or "")

    def test_parse_analytical_notebook(self) -> None:
        raw = json.dumps(_analytical_notebook())
        parsed, err = parse_notebook(raw, filename="presencialidad.ipynb")

        self.assertIsNone(err)
        assert parsed is not None
        self.assertEqual(parsed.title, "Análisis de Presencialidad")
        self.assertEqual(parsed.n_markdown, 2)
        self.assertEqual(parsed.n_code, 3)
        self.assertEqual(parsed.n_with_plot, 1)
        self.assertEqual(parsed.n_errors, 1)

        plot_cell = parsed.cells[2]
        self.assertTrue(plot_cell.has_plot)
        self.assertIn("Gráfico", plot_cell.outputs_summary or "")

        error_cell = parsed.cells[4]
        self.assertTrue(error_cell.has_error)
        self.assertIn("KeyError", error_cell.outputs_summary or "")

    def test_parse_from_bytesio(self) -> None:
        raw = json.dumps(_minimal_notebook()).encode("utf-8")
        parsed, err = parse_notebook(BytesIO(raw), filename="stream.ipynb")

        self.assertIsNone(err)
        assert parsed is not None
        self.assertEqual(parsed.cell_count, 2)

    def test_parse_invalid_notebook(self) -> None:
        parsed, err = parse_notebook("{not valid json", filename="bad.ipynb")

        self.assertIsNone(parsed)
        self.assertIsNotNone(err)
        self.assertIn("No se pudo leer", err or "")

    def test_extract_headings(self) -> None:
        raw = json.dumps(_analytical_notebook())
        parsed, _ = parse_notebook(raw, filename="presencialidad.ipynb")
        assert parsed is not None

        headings = extract_headings(parsed)
        self.assertIn("Análisis de Presencialidad", headings)
        self.assertIn("Objetivo", headings)
        self.assertIn("Conclusiones", headings)

    def test_build_llm_context_includes_key_sections(self) -> None:
        raw = json.dumps(_analytical_notebook())
        parsed, _ = parse_notebook(raw, filename="presencialidad.ipynb")
        assert parsed is not None

        context = build_llm_context(parsed)

        self.assertIn("NOTEBOOK: presencialidad.ipynb", context)
        self.assertIn("Análisis de Presencialidad", context)
        self.assertIn("Títulos/secciones:", context)
        self.assertIn("Celda 1 [code]", context)
        self.assertIn("[Output]:", context)
        self.assertIn("[Incluye gráfico]", context)
        self.assertIn("[Celda con error de ejecución]", context)
        self.assertIn("tasa_asistencia", context)

    def test_build_llm_context_truncation(self) -> None:
        raw = json.dumps(_analytical_notebook())
        parsed, _ = parse_notebook(raw, filename="presencialidad.ipynb")
        assert parsed is not None

        context = build_llm_context(parsed, max_chars=200)
        self.assertIn("contexto truncado", context)
        self.assertLessEqual(len(context), 200)


if __name__ == "__main__":
    unittest.main()
