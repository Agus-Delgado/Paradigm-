"""Constantes de tema, umbrales y rutas para la app Streamlit v2."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Paleta médica / clínica
COLOR_PRIMARY = "#0D9488"  # teal
COLOR_SECONDARY = "#1E293B"  # slate
COLOR_ACCENT = "#F97316"  # coral (alertas)
COLOR_SUCCESS = "#059669"
COLOR_MUTED = "#64748B"
COLOR_BG_LIGHT = "#F8FAFC"
COLOR_BG_DARK = "#0F172A"

# Umbrales de recomendación no-show (probabilidad 0–1)
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
