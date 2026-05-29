"""Clasificación de intención por reglas (sin ML)."""

from __future__ import annotations

import re
import unicodedata

from core.ai_analytics.types import Intent

# Prioridad en empates (mayor índice = gana)
_INTENT_PRIORITY: list[Intent] = [
    "unknown",
    "filter",
    "compare",
    "search",
    "summarize",
    "explain",
    "detect_anomaly",
]

_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    "detect_anomaly": (
        "anomal",
        "anomaly",
        "inusual",
        "unusual",
        "outlier",
        "atipic",
        "atípic",
        "raro",
        "extremo",
        "valores raros",
    ),
    "explain": (
        "explic",
        "explain",
        "describe",
        "descripcion",
        "descripción",
        "que es",
        "qué es",
        "como funciona",
        "cómo funciona",
        "entender",
        "significa",
    ),
    "summarize": (
        "resum",
        "summar",
        "insight",
        "analiz",
        "analyze",
        "overview",
        "clave",
        "panorama",
        "revisar primero",
        "review first",
        "deberia revisar",
        "debería revisar",
        "primera pasada",
        "ejecutiv",
    ),
    "search": (
        "busc",
        "search",
        "encontr",
        "find",
        "nulo",
        "null",
        "missing",
        "faltan",
        "falta",
        "que columnas",
        "qué columnas",
        "which column",
        "donde hay",
        "dónde hay",
    ),
    "compare": (
        "compar",
        "compare",
        " versus ",
        " vs ",
        "entre ",
        "diferencia",
        "difference",
        "peor",
        "mejor",
        "underperform",
        "bajo rendimiento",
        "mayor",
        "menor",
    ),
    "filter": (
        "filtr",
        "filter",
        "solo ",
        "solamente",
        "mostrar filas",
        "where ",
        "donde ",
        "dónde ",
        "restring",
        "subset",
    ),
}


def _normalize_query(query: str) -> str:
    text = query.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text)
    return text


def classify_intent(query: str) -> Intent:
    """Clasifica la pregunta del usuario por coincidencia de palabras clave."""
    norm = _normalize_query(query)
    if not norm:
        return "unknown"

    scores: dict[Intent, int] = {k: 0 for k in _KEYWORDS}
    for intent, keywords in _KEYWORDS.items():
        for kw in keywords:
            if kw in norm:
                scores[intent] += 1

    best_score = max(scores.values())
    if best_score == 0:
        return "unknown"

    candidates = [intent for intent, sc in scores.items() if sc == best_score]
    if len(candidates) == 1:
        return candidates[0]

    priority_rank = {intent: i for i, intent in enumerate(_INTENT_PRIORITY)}
    return max(candidates, key=lambda i: priority_rank[i])
