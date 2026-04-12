"""Ejecuta la batería de checks y opcionalmente escribe el reporte."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from paradigm.io.paths import DB_PATH, DEFAULT_QUALITY_REPORT
from paradigm.quality.checks import ALL_CHECKS
from paradigm.quality.report import write_report
from paradigm.quality.results import CheckResult, Severity


def run_checks(db_path: Path | None = None) -> list[CheckResult]:
    path = db_path or DB_PATH
    if not path.is_file():
        raise FileNotFoundError(
            f"No existe la base {path}. Ejecutá primero: python scripts/build_sqlite_mart.py"
        )
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        results: list[CheckResult] = []
        for fn in ALL_CHECKS:
            results.append(fn(conn))
        return results
    finally:
        conn.close()


def exit_code_from_results(results: list[CheckResult]) -> int:
    if any(r.severity == Severity.FAIL for r in results):
        return 1
    return 0


def run_and_report(
    db_path: Path | None = None,
    report_path: Path | None = None,
) -> tuple[list[CheckResult], int]:
    """Ejecuta checks, escribe Markdown y devuelve (resultados, código de salida)."""
    path = db_path or DB_PATH
    out = report_path or DEFAULT_QUALITY_REPORT
    results = run_checks(path)
    write_report(results, path, out)
    return results, exit_code_from_results(results)
