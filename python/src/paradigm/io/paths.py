"""Rutas raíz del repositorio Paradigm (uso desde scripts con PYTHONPATH=python/src)."""

from __future__ import annotations

from pathlib import Path

# python/src/paradigm/io/paths.py -> parents[4] = raíz del repo
_REPO = Path(__file__).resolve().parents[4]

REPO_ROOT: Path = _REPO
PROCESSED_DIR: Path = _REPO / "data" / "processed"
DB_PATH: Path = PROCESSED_DIR / "paradigm_mart.db"
REPORTS_DIR: Path = _REPO / "reports"
DEFAULT_QUALITY_REPORT: Path = REPORTS_DIR / "quality_report.md"
ML_EXPERIMENTS_DIR: Path = _REPO / "ml" / "experiments"
ML_FIGURES_DIR: Path = _REPO / "ml" / "figures"
SHAP_BUNDLE_PATH: Path = PROCESSED_DIR / "shap_bundle.joblib"
SHAP_SUMMARY_PNG: Path = ML_FIGURES_DIR / "shap_summary_beeswarm.png"
