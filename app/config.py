"""Constantes de tema, umbrales y rutas para la app Streamlit v2."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ── Paleta premium dark — Paradigm ────────────────────────────────────────
COLOR_PRIMARY   = "#00f5ff"   # cyan — CTA, primary chart series
COLOR_ACCENT    = "#38bdf8"   # sky-400 — secondary chart series / highlights
COLOR_SECONDARY = "#e0f2fe"   # body text (light on dark bg)
COLOR_TEXT      = "#e0f2fe"   # alias for body text
COLOR_BG_MAIN   = "#0a2540"   # deep navy background
COLOR_BG_CARD   = "#13294b"   # card surface
COLOR_BG_DARK   = "#0a2540"   # legacy alias — always dark
COLOR_BG_LIGHT  = "#0a2540"   # legacy alias — always dark
COLOR_BORDER    = "#00f5ff33" # subtle cyan border
COLOR_MUTED     = "#94a3b8"   # muted text / minor labels
COLOR_SUCCESS   = "#10b981"   # green — low impact badge / positive delta
COLOR_WARNING   = "#f59e0b"   # amber — medium impact badge

# ── Umbrales de recomendación no-show (probabilidad 0–1) ──────────────────
THRESHOLD_HIGH   = 0.30
THRESHOLD_MEDIUM = 0.15

RECOMMENDATIONS = {
    "high":   "Priorizar recordatorio telefónico y confirmación activa",
    "medium": "Enviar recordatorio estándar (SMS / email)",
    "low":    "Riesgo bajo — flujo habitual de confirmación",
}

SYNTHETIC_BANNER = (
    "Datos 100 % sintéticos con fines demostrativos. "
    "No representan pacientes, prestadores ni instituciones reales."
)

BUILD_COMMANDS = """python scripts/generate_paradigm_v2_synthetic.py
python scripts/build_sqlite_mart.py"""

TRAIN_COMMAND = "python scripts/train_no_show.py"

MODEL_FILES = {
    "Random Forest":      "no_show_random_forest.joblib",
    "Logistic Regression": "no_show_logistic.joblib",
}
