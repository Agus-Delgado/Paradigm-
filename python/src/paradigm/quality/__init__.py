"""Validación y reportes de calidad sobre el mart SQLite."""

from paradigm.quality.runner import exit_code_from_results, run_and_report, run_checks

__all__ = ["run_checks", "run_and_report", "exit_code_from_results"]
