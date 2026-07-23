"""Constantes de tema, umbrales y rutas para la app Streamlit v2.

Paleta Observatory: docs/PARADIGM_DESIGN_SYSTEM.md
Fuente visual principal: assets/css/custom.css (--pd-*).
Este módulo espeja hex para Plotly / HTML inline; no diverge de CSS.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# ── Versión demo (footer / README) ─────────────────────────────────────────
APP_VERSION = "2.2.0"
LAST_UPDATE = "2026-07-22"

# ── Paradigm Observatory tokens (mirror of --pd-* in custom.css) ───────────
COLOR_BG_MAIN = "#0B1622"
COLOR_BG_SECONDARY = "#111C2A"
COLOR_SURFACE = "#162433"
COLOR_SURFACE_ELEVATED = "#1C2E40"

COLOR_TEXT_PRIMARY = "#E6EDF5"
COLOR_TEXT_SECONDARY = "#A8B6C7"
COLOR_TEXT_MUTED = "#7A8A9C"

COLOR_SIGNAL = "#6FA8A0"
COLOR_STRUCTURE = "#7691A8"
COLOR_INTERPRETATION = "#8B9BC4"
COLOR_DECISION = "#C4A46C"
COLOR_ACTION = "#D97B5C"
COLOR_RISK = "#C45C6A"

COLOR_SUCCESS = "#5FAE8E"
COLOR_WARNING = "#C9A05A"
COLOR_INFO = "#8B9BC4"

COLOR_BORDER_SUBTLE = "#2A3D52"
COLOR_BORDER_STRONG = "#3D5570"

# ── Legacy aliases (nombres públicos usados por UI / plots / ML) ────────────
# Mapear a Observatory; no eliminar mientras haya imports.
COLOR_PRIMARY = COLOR_SIGNAL  # series / acento de dato (no CTA)
COLOR_PRIMARY_SOFT = COLOR_SIGNAL  # métricas, labels suaves
COLOR_CHART = COLOR_SIGNAL  # series principales Plotly
COLOR_ACCENT = COLOR_INTERPRETATION  # series secundarias
COLOR_SECONDARY = COLOR_TEXT_PRIMARY  # body text (legacy name)
COLOR_TEXT = COLOR_TEXT_PRIMARY
COLOR_BG_CARD = COLOR_SURFACE
COLOR_BG_DARK = COLOR_BG_MAIN
COLOR_BG_LIGHT = COLOR_BG_MAIN  # legacy alias — always dark
COLOR_BORDER = COLOR_BORDER_SUBTLE
COLOR_MUTED = COLOR_TEXT_MUTED

# ── Umbrales de recomendación no-show (probabilidad 0–1) ──────────────────
THRESHOLD_HIGH = 0.30
THRESHOLD_MEDIUM = 0.15

RECOMMENDATIONS = {
    "high": "Priorizar recordatorio telefónico y confirmación activa",
    "medium": "Enviar recordatorio estándar (SMS / email)",
    "low": "Riesgo bajo — flujo habitual de confirmación",
}

SYNTHETIC_BANNER = (
    "Datos 100 % sintéticos con fines demostrativos. "
    "No representan pacientes, prestadores ni instituciones reales."
)

BUILD_COMMANDS = """python scripts/generate_paradigm_v2_synthetic.py
python scripts/build_sqlite_mart.py"""

TRAIN_COMMAND = "python scripts/train_no_show.py"

MODEL_FILES = {
    "Random Forest": "no_show_random_forest.joblib",
    "Logistic Regression": "no_show_logistic.joblib",
}
