"""Rutas raíz del repositorio Paradigm (uso desde scripts con PYTHONPATH=python/src)."""

from __future__ import annotations

from pathlib import Path

# python/src/paradigm/io/paths.py -> parents[4] = raíz del repo
_REPO = Path(__file__).resolve().parents[4]

REPO_ROOT: Path = _REPO
DB_PATH: Path = _REPO / "data" / "processed" / "paradigm_mart.db"
REPORTS_DIR: Path = _REPO / "reports"
DEFAULT_QUALITY_REPORT: Path = REPORTS_DIR / "quality_report.md"
ML_EXPERIMENTS_DIR: Path = _REPO / "ml" / "experiments"
