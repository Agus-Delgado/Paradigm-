"""Constantes de tema, umbrales y rutas para la app Streamlit v2."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# ── Versión demo (footer / README) ─────────────────────────────────────────
APP_VERSION = "2.2.0"
LAST_UPDATE = "2026-07-22"

# ── Paleta premium dark — tonos profesionales (menos fluorescencia) ────────
COLOR_PRIMARY   = "#00f5ff"   # cyan marca — acentos y CTA (usar con moderación)
COLOR_PRIMARY_SOFT = "#5ec8d4"  # cyan apagado — áreas grandes, métricas
COLOR_CHART     = "#38b8c7"   # series principales en gráficos
COLOR_ACCENT    = "#5b9cb8"   # sky muted — series secundarias
COLOR_SECONDARY = "#e0f2fe"   # body text (light on dark bg)
COLOR_TEXT      = "#e0f2fe"   # alias for body text
COLOR_BG_MAIN   = "#0a2540"   # deep navy background
COLOR_BG_CARD   = "#13294b"   # card surface
COLOR_BG_DARK   = "#0a2540"   # legacy alias — always dark
COLOR_BG_LIGHT  = "#0a2540"   # legacy alias — always dark
COLOR_BORDER    = "#5ec8d433" # subtle cyan border (muted)
COLOR_MUTED     = "#94a3b8"   # muted text / minor labels
COLOR_SUCCESS   = "#34d399"   # green muted — delta positivo / éxito
COLOR_WARNING   = "#d4a24a"   # amber muted — advertencias / impacto medio

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
