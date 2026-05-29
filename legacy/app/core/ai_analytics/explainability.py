"""Confianza, explicación y siguientes pasos para respuestas conversacionales."""

from __future__ import annotations

from core.ai_analytics.types import Confidence, Intent
from core.findings import Finding
from core.profiling import DatasetProfile

_INTENT_EXPLANATION: dict[Intent, str] = {
    "summarize": (
        "Respuesta generada por reglas sobre el perfil del dataset, hallazgos de calidad "
        "y métricas opcionales del consultorio."
    ),
    "explain": (
        "Descripción basada en tipos inferidos, dimensiones del archivo y estimación heurística de calidad."
    ),
    "detect_anomaly": (
        "Valores atípicos detectados con el método de rango intercuartílico (IQR × 1.5) "
        "en columnas numéricas; z-score solo como nota cuando hay suficientes filas."
    ),
    "search": (
        "Búsqueda por coincidencia de palabras clave en nombres de columnas y/o reporte de nulos del perfil."
    ),
    "compare": (
        "Comparación determinística entre grupos categóricos y medias numéricas, "
        "o métricas del esquema de consultorio cuando aplica."
    ),
    "filter": (
        "Sugerencias de filtro derivadas de columnas filtrables y valores observados; "
        "no modifica los filtros de la barra lateral."
    ),
    "unknown": (
        "No se reconoció una intención clara; se muestra orientación general."
    ),
}

_NEXT_STEP: dict[Intent, str] = {
    "summarize": "Revisá la pestaña Hallazgos y el perfil por columna en Resumen para profundizar.",
    "explain": "Explorá columnas concretas en la pestaña Gráficos o aplicá filtros en la barra lateral.",
    "detect_anomaly": "Validá los valores señalados en Exploración y contrastá con el contexto de negocio.",
    "search": "Usá Exploración con filtros en columnas relevantes para aislar filas.",
    "compare": "Ajustá filtros por segmento en la barra lateral y compará gráficos por columna.",
    "filter": "Configurá los filtros sugeridos en la barra lateral (pestaña Exploración / Gráficos).",
    "unknown": "Probá una de las preguntas de ejemplo o reformulá con palabras como resumen, nulos o anomalías.",
}


def findings_to_strings(findings: list[Finding], limit: int = 6) -> list[str]:
    return [f.message for f in findings[:limit]]


def compute_confidence(
    intent: Intent,
    profile: DatasetProfile,
    match_strength: int,
    n_findings: int,
) -> Confidence:
    rows = profile.row_count
    if intent == "unknown" or rows == 0:
        return "low"
    if rows < 5:
        return "low"

    strong = match_strength >= 2 or (match_strength >= 1 and n_findings >= 2)
    if rows >= 20 and strong and n_findings >= 1:
        return "high"
    if rows >= 10 and (strong or n_findings >= 1):
        return "medium"
    return "low" if rows < 10 else "medium"


def build_explanation(intent: Intent, extra: str | None = None) -> str:
    base = _INTENT_EXPLANATION.get(intent, _INTENT_EXPLANATION["unknown"])
    if extra:
        return f"{base} {extra}"
    return base


def suggested_next_step(intent: Intent) -> str:
    return _NEXT_STEP.get(intent, _NEXT_STEP["unknown"])
