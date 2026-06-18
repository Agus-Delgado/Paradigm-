"""Natural Language → SQL híbrido (LLM + heurístico con fallback)."""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from app.config.llm_config import is_llm_available
from app.conversational.legacy_bridge import classify_intent
from app.conversational.llm_security import validate_llm_sql
from app.conversational.sql_engine import TABLE_NAME
from app.conversational.types import Domain

logger = logging.getLogger(__name__)

SQL_ENGINE = Literal["llm", "heuristic"]

_DOMAIN_METRIC_HINTS: dict[Domain, tuple[str, ...]] = {
    "finance": ("variacion_pct", "variacion", "desvio", "desviacion", "real", "presupuesto", "monto"),
    "healthcare_clinic": ("ingreso_neto", "monto", "importe", "costo"),
    "healthcare_mart": ("net_revenue", "amount", "revenue"),
    "operations": ("defectos", "defecto", "tiempo_ciclo", "scrap", "unidades"),
    "generic": (),
}

_DOMAIN_SEGMENT_HINTS: dict[Domain, tuple[str, ...]] = {
    "finance": ("centro_costo", "departamento", "cuenta", "cliente"),
    "healthcare_clinic": ("especialidad", "medico", "cobertura_medica", "medio_pago", "estado_turno"),
    "healthcare_mart": ("specialty_name", "provider_label", "channel_code", "status_code"),
    "operations": ("planta", "linea", "turno", "producto"),
    "generic": (),
}

_QUERY_METRIC_WORDS = (
    "desvio",
    "desviacion",
    "variacion",
    "outlier",
    "anomal",
    "mayor",
    "menor",
    "promedio",
    "media",
    "total",
    "suma",
    "ingreso",
    "costo",
    "monto",
    "defecto",
)

_QUERY_SEGMENT_WORDS = (
    "cliente",
    "customer",
    "centro",
    "departamento",
    "especialidad",
    "planta",
    "linea",
    "segmento",
    "categoria",
    "estado",
    "canal",
    "proveedor",
)


def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(query: str) -> list[str]:
    return [t for t in _normalize(query).split() if len(t) >= 2]


def _score_column(col: str, tokens: list[str], hints: tuple[str, ...]) -> int:
    norm_col = _normalize(col).replace("_", " ")
    score = 0
    for tok in tokens:
        if tok in norm_col or norm_col in tok:
            score += 3
    for hint in hints:
        hint_norm = _normalize(hint)
        if hint_norm == _normalize(col):
            score += 10
        elif hint_norm in norm_col:
            score += 5
    return score


def match_columns(
    query: str,
    columns: list[str],
    *,
    logical_types: dict[str, str],
    want: str,
    domain: Domain,
    hints: tuple[str, ...] = (),
) -> str | None:
    """Resuelve la mejor columna según tokens del query y dominio."""
    tokens = _tokens(query)
    domain_hints = _DOMAIN_METRIC_HINTS.get(domain, ()) if want == "numeric" else _DOMAIN_SEGMENT_HINTS.get(domain, ())
    all_hints = hints + domain_hints

    candidates = [
        c
        for c in columns
        if logical_types.get(c, "text") == want or (want == "numeric" and logical_types.get(c) == "numeric")
    ]
    if want == "categorical":
        candidates = [c for c in columns if logical_types.get(c, "text") in ("categorical", "boolean", "text")]
    if not candidates:
        return None

    scored = [(c, _score_column(c, tokens, all_hints)) for c in candidates]
    scored.sort(key=lambda x: (-x[1], x[0]))
    if scored[0][1] > 0:
        return scored[0][0]

    word_pool = _QUERY_METRIC_WORDS if want == "numeric" else _QUERY_SEGMENT_WORDS
    for word in word_pool:
        if word in _normalize(query):
            for c in candidates:
                if word in _normalize(c):
                    return c

    return candidates[0] if candidates else None


def pick_compare_pair(
    query: str,
    columns: list[str],
    logical_types: dict[str, str],
    domain: Domain,
) -> tuple[str | None, str | None]:
    segment = match_columns(query, columns, logical_types=logical_types, want="categorical", domain=domain)
    metric = match_columns(query, columns, logical_types=logical_types, want="numeric", domain=domain)
    if segment and metric:
        return segment, metric

    cats = [c for c in columns if logical_types.get(c) in ("categorical", "boolean")]
    nums = [c for c in columns if logical_types.get(c) == "numeric"]
    return (cats[0] if cats else None, nums[0] if nums else None)


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _limit_clause(query: str, default: int = 20) -> int:
    norm = _normalize(query)
    m = re.search(r"\b(top|primeros?|ultimos?|últimos?)\s+(\d+)\b", norm)
    if m:
        return min(int(m.group(2)), 500)
    if any(w in norm for w in ("todos", "completo", "all")):
        return 500
    return default


@dataclass
class SQLResult:
    """Resultado enriquecido de NL→SQL (LLM o heurístico)."""

    sql: str
    explanation: str
    engine: SQL_ENGINE
    confidence: str | None = None
    sources: list[str] = field(default_factory=list)
    used_llm: bool = False
    fallback_reason: str | None = None


def _generate_sql_heuristic(
    query: str,
    df: pd.DataFrame,
    logical_types: dict[str, str],
    domain: Domain,
) -> tuple[str, str]:
    """
    Genera SQL heurístico editable (motor determinístico original).
    Returns: (sql, explanation)
    """
    columns = list(df.columns)
    intent = classify_intent(query)
    limit = _limit_clause(query)
    t = TABLE_NAME
    norm = _normalize(query)

    if intent == "compare" or any(w in norm for w in ("compar", "versus", " vs ", "entre", "por")):
        seg, met = pick_compare_pair(query, columns, logical_types, domain)
        if seg and met:
            sql = (
                f"SELECT {_quote_ident(seg)} AS segmento,\n"
                f"       AVG({_quote_ident(met)}) AS promedio,\n"
                f"       COUNT(*) AS filas\n"
                f"FROM {t}\n"
                f"GROUP BY {_quote_ident(seg)}\n"
                f"ORDER BY promedio DESC\n"
                f"LIMIT {limit}"
            )
            return sql, f"Comparación agrupada: promedio de «{met}» por «{seg}»."

    if intent == "detect_anomaly" or any(
        w in norm for w in ("anomal", "outlier", "atipic", "desvio", "desviacion", "inusual", "extremo")
    ):
        metric = match_columns(query, columns, logical_types=logical_types, want="numeric", domain=domain)
        if metric:
            sql = (
                f"SELECT *,\n"
                f"       ABS({_quote_ident(metric)} - (SELECT AVG({_quote_ident(metric)}) FROM {t})) AS desvio_abs\n"
                f"FROM {t}\n"
                f"WHERE {_quote_ident(metric)} IS NOT NULL\n"
                f"ORDER BY desvio_abs DESC\n"
                f"LIMIT {limit}"
            )
            return sql, f"Filas ordenadas por desvío absoluto respecto al promedio de «{metric}»."

    if intent == "search" or any(w in norm for w in ("nulo", "null", "faltan", "missing", "columna")):
        parts = []
        for col in columns[:12]:
            qc = _quote_ident(col)
            parts.append(
                f"SELECT '{col}' AS columna, COUNT(*) AS filas, "
                f"COUNT(*) - COUNT({qc}) AS nulos "
                f"FROM {t}"
            )
        sql = "\nUNION ALL\n".join(parts) + "\nORDER BY nulos DESC"
        return sql, "Conteo de nulos por columna (hasta 12 columnas)."

    if intent == "filter" or any(w in norm for w in ("filtr", "solo", "donde", "mostrar")):
        seg = match_columns(query, columns, logical_types=logical_types, want="categorical", domain=domain)
        if seg and seg in df.columns:
            top = df[seg].astype(str).value_counts().head(1)
            if not top.empty:
                val = str(top.index[0]).replace("'", "''")
                sql = (
                    f"SELECT *\nFROM {t}\n"
                    f"WHERE CAST({_quote_ident(seg)} AS TEXT) = '{val}'\n"
                    f"LIMIT {limit}"
                )
                return sql, f"Filtro sugerido: «{seg}» = '{top.index[0]}' (valor más frecuente)."

    if intent == "summarize" or any(w in norm for w in ("resum", "panorama", "overview", "cuant")):
        sql = (
            f"SELECT COUNT(*) AS total_filas,\n"
            f"       COUNT(DISTINCT {_quote_ident(columns[0])}) AS unicos_primera_columna\n"
            f"FROM {t}"
        )
        return sql, "Resumen rápido del dataset."

    # Fallback: top valores por segmento + métrica de dominio
    seg, met = pick_compare_pair(query, columns, logical_types, domain)
    if seg and met:
        sql = (
            f"SELECT {_quote_ident(seg)}, {_quote_ident(met)}, COUNT(*) AS filas\n"
            f"FROM {t}\n"
            f"GROUP BY {_quote_ident(seg)}, {_quote_ident(met)}\n"
            f"ORDER BY {_quote_ident(met)} DESC\n"
            f"LIMIT {limit}"
        )
        return sql, f"Consulta sugerida por defecto: «{met}» agrupado con «{seg}»."

    sql = f"SELECT * FROM {t} LIMIT {min(limit, 50)}"
    return sql, "No se detectó un patrón específico; consulta de exploración básica."


def _heuristic_sql_result(
    query: str,
    df: pd.DataFrame,
    logical_types: dict[str, str],
    domain: Domain,
    *,
    fallback_reason: str | None = None,
) -> SQLResult:
    sql_text, explanation = _generate_sql_heuristic(query, df, logical_types, domain)
    return SQLResult(
        sql=sql_text,
        explanation=explanation,
        engine="heuristic",
        confidence="low",
        sources=["heuristic:nl_to_sql"],
        used_llm=False,
        fallback_reason=fallback_reason,
    )


def generate_sql_llm_enhanced(
    natural_query: str,
    df: pd.DataFrame,
    logical_types: dict[str, str],
    domain: Domain,
    *,
    force_heuristic: bool = False,
) -> SQLResult:
    """
    Genera SQL vía LLM (RAG + schema) con fallback al motor heurístico.

    Usa ``llm_service.generate_sql_llm`` cuando el proveedor está disponible.
    """
    if force_heuristic or not is_llm_available():
        reason = "LLM deshabilitado o no disponible" if not force_heuristic else "force_heuristic=True"
        result = _heuristic_sql_result(natural_query, df, logical_types, domain, fallback_reason=reason)
        logger.info("NL→SQL engine=heuristic (sin LLM) query=%r", natural_query[:120])
        return result

    from app.conversational.llm_service import generate_sql_llm

    analyst = generate_sql_llm(natural_query, df, logical_types, domain)
    sql_text = (analyst.sql or "").strip()
    explanation = (analyst.explanation or analyst.insight or "").strip()

    if analyst.used_llm and sql_text and validate_llm_sql(sql_text)[0]:
        result = SQLResult(
            sql=sql_text,
            explanation=explanation or "Consulta generada por analista LLM.",
            engine="llm",
            confidence=analyst.confidence,
            sources=list(analyst.sources),
            used_llm=True,
            fallback_reason=None,
        )
        logger.info(
            "NL→SQL engine=llm confidence=%s query=%r sources=%s",
            result.confidence,
            natural_query[:120],
            result.sources,
        )
        return result

    reason = analyst.fallback_reason or "SQL LLM inválido o no seguro"
    result = _heuristic_sql_result(natural_query, df, logical_types, domain, fallback_reason=reason)
    logger.warning(
        "NL→SQL engine=heuristic (fallback) reason=%s query=%r",
        reason,
        natural_query[:120],
    )
    return result


def generate_sql(
    query: str,
    df: pd.DataFrame,
    logical_types: dict[str, str],
    domain: Domain,
) -> tuple[str, str]:
    """
    Genera SQL para el dataset activo.

    Intenta primero el analista LLM; si no está disponible, falla o el SQL
    no pasa ``is_safe_sql``, usa el motor heurístico determinístico.

    Returns: (sql, explanation) — firma compatible con consumidores existentes.
    """
    result = generate_sql_llm_enhanced(query, df, logical_types, domain)
    return result.sql, result.explanation
