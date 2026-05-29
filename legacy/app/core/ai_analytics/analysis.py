"""Orquestador de análisis conversacional determinístico."""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

from core.ai_analytics.explainability import (
    build_explanation,
    compute_confidence,
    findings_to_strings,
    suggested_next_step,
)
from core.ai_analytics.insights import (
    build_dataset_overview,
    compare_categorical_numeric,
    compare_clinic_especialidad_ingreso,
    compare_clinic_estado,
    detect_numeric_outliers,
    missing_columns_report,
    pick_compare_pair,
    search_columns_by_tokens,
    suggest_filters,
    top_categories_insights,
    zscore_outlier_note,
)
from core.ai_analytics.intent import classify_intent
from core.ai_analytics.types import ConversationalResult, Intent
from core.clinic_operational_insights import (
    build_clinic_operational_insights,
    clinic_operational_insights_available,
)
from core.clinic_operational_kpis import clinic_kpis_available, compute_clinic_kpis
from core.findings import Finding
from core.profiling import DatasetProfile, count_logical_types, estimate_dataset_quality

_LOGICAL_LABEL_ES: dict[str, str] = {
    "numeric": "Numérico",
    "categorical": "Categórico",
    "boolean": "Booleano",
    "datetime": "Fecha / hora",
    "text": "Texto",
    "id": "Identificador",
}


def _normalize_tokens(query: str) -> list[str]:
    text = query.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\s]", " ", text)
    return [t for t in text.split() if len(t) >= 2]


def _intent_match_strength(query: str, intent: Intent) -> int:
    from core.ai_analytics.intent import _KEYWORDS, _normalize_query

    norm = _normalize_query(query)
    if intent == "unknown":
        return 0
    return sum(1 for kw in _KEYWORDS.get(intent, ()) if kw in norm)


def _empty_result(intent: Intent, title: str, summary: str) -> ConversationalResult:
    return ConversationalResult(
        intent=intent,
        title=title,
        summary=summary,
        findings=[],
        data_used=[],
        confidence="low",
        explanation=build_explanation(intent),
        suggested_next_step=suggested_next_step(intent),
    )


def _finalize(
    intent: Intent,
    title: str,
    summary: str,
    findings: list[str],
    data_used: list[str],
    profile: DatasetProfile,
    query: str,
    extra_explanation: str | None = None,
) -> ConversationalResult:
    strength = _intent_match_strength(query, intent)
    confidence = compute_confidence(intent, profile, strength, len(findings))
    return ConversationalResult(
        intent=intent,
        title=title,
        summary=summary,
        findings=findings,
        data_used=data_used,
        confidence=confidence,
        explanation=build_explanation(intent, extra_explanation),
        suggested_next_step=suggested_next_step(intent),
    )


def _handle_summarize(
    df: pd.DataFrame,
    profile: DatasetProfile,
    logical_types: dict[str, str],
    findings: list[Finding],
    query: str,
) -> ConversationalResult:
    quality_label, _ = estimate_dataset_quality(profile)
    overview = build_dataset_overview(df, profile, logical_types)
    finding_msgs = findings_to_strings(findings)
    top_cats = top_categories_insights(df, logical_types)

    all_findings = finding_msgs + top_cats
    data_used = ["profile", "logical_types", "build_findings"]

    if clinic_kpis_available(df):
        k = compute_clinic_kpis(df)
        data_used.extend(["estado_turno", "especialidad", "ingreso_neto"])
        all_findings.append(
            f"Turnos: {k['n_turnos']:,}; asistido {k['pct_asistido']:.1f}%, "
            f"ausente {k['pct_ausente']:.1f}%, ingreso neto total {k['ingreso_neto_total']:,.2f}."
        )

    if clinic_operational_insights_available(df):
        op = build_clinic_operational_insights(df)
        data_used.append("clinic_operational_insights")
        all_findings.extend(findings_to_strings(op, limit=2))

    summary = (
        f"Resumen del dataset ({profile.row_count:,} filas, calidad estimada {quality_label}). "
        + (overview[0] if overview else "")
    )

    return _finalize(
        "summarize",
        "Resumen e insights clave",
        summary,
        overview + all_findings,
        data_used,
        profile,
        query,
    )


def _handle_explain(
    profile: DatasetProfile,
    logical_types: dict[str, str],
    query: str,
) -> ConversationalResult:
    type_counts = count_logical_types(profile)
    quality_label, quality_hint = estimate_dataset_quality(profile)

    type_lines = [
        f"«{col}»: {_LOGICAL_LABEL_ES.get(lt, lt)}"
        for col, lt in list(logical_types.items())[:12]
    ]
    if len(logical_types) > 12:
        type_lines.append(f"… y {len(logical_types) - 12} columnas más.")

    findings = [
        f"Filas: {profile.row_count:,}; columnas: {profile.column_count}; "
        f"duplicados: {profile.duplicate_rows:,}; memoria ~{profile.memory_mb:.2f} MiB.",
        f"Calidad estimada: {quality_label} — {quality_hint}",
        "Distribución de tipos: " + ", ".join(f"{k}={v}" for k, v in type_counts.items()) + ".",
    ] + type_lines

    summary = (
        "Este dataset fue perfilado con reglas heurísticas (sin ML): se infieren tipos lógicos "
        "y se estima calidad a partir de nulos y duplicados."
    )

    return _finalize(
        "explain",
        "Explicación del dataset",
        summary,
        findings,
        list(logical_types.keys())[:15] or ["dataset"],
        profile,
        query,
    )


def _handle_detect_anomaly(
    df: pd.DataFrame,
    profile: DatasetProfile,
    logical_types: dict[str, str],
    query: str,
) -> ConversationalResult:
    outlier_findings, data_used = detect_numeric_outliers(df, logical_types)

    for col in data_used[:2]:
        note = zscore_outlier_note(df, col)
        if note:
            outlier_findings.append(note)

    summary = (
        "Análisis de valores atípicos en columnas numéricas usando IQR (1.5×). "
        f"Se evaluaron {sum(1 for c in df.columns if logical_types.get(c) == 'numeric')} columnas numéricas."
    )

    return _finalize(
        "detect_anomaly",
        "Detección de anomalías",
        summary,
        outlier_findings,
        data_used or ["columnas numéricas"],
        profile,
        query,
    )


def _handle_search(
    query: str,
    df: pd.DataFrame,
    profile: DatasetProfile,
    logical_types: dict[str, str],
) -> ConversationalResult:
    norm = query.lower()
    missing_kw = any(k in norm for k in ("nulo", "null", "missing", "faltan", "falta"))

    if missing_kw:
        findings, data_used = missing_columns_report(profile)
        summary = "Columnas con valores nulos, ordenadas por porcentaje de nulos."
        return _finalize("search", "Búsqueda: valores nulos", summary, findings, data_used, profile, query)

    tokens = _normalize_tokens(query)
    stop = {
        "que", "qué", "cual", "cuál", "columnas", "columna", "buscar", "search",
        "find", "donde", "dónde", "hay", "tiene", "tienen", "the", "which",
    }
    tokens = [t for t in tokens if t not in stop]

    findings, data_used = search_columns_by_tokens(df, profile, tokens)
    if not findings:
        findings = [
            "No se encontraron columnas por nombre. Probá preguntar por «nulos» o usar el nombre exacto de una columna."
        ]
        data_used = []

    summary = "Resultados de búsqueda sobre nombres de columnas y perfil."
    return _finalize("search", "Búsqueda en el dataset", summary, findings, data_used, profile, query)


def _handle_compare(
    df: pd.DataFrame,
    profile: DatasetProfile,
    logical_types: dict[str, str],
    query: str,
) -> ConversationalResult:
    findings: list[str] = []
    data_used: list[str] = []

    clinic_est = compare_clinic_estado(df)
    if clinic_est:
        findings.append(clinic_est)
        data_used.append("estado_turno")

    clinic_ing = compare_clinic_especialidad_ingreso(df)
    if clinic_ing:
        findings.append(clinic_ing)
        data_used.extend(["especialidad", "ingreso_neto"])

    pair = pick_compare_pair(df, logical_types)
    if pair:
        cat_col, num_col = pair
        msg = compare_categorical_numeric(df, cat_col, num_col)
        if msg:
            findings.append(msg)
            data_used.extend([cat_col, num_col])

    if not findings:
        findings.append(
            "No hay suficientes columnas categóricas y numéricas para una comparación automática."
        )

    summary = "Comparación entre segmentos o grupos detectados en el dataset completo."
    return _finalize("compare", "Comparación de segmentos", summary, findings, data_used, profile, query)


def _handle_filter(
    df: pd.DataFrame,
    profile: DatasetProfile,
    logical_types: dict[str, str],
    query: str,
) -> ConversationalResult:
    tokens = _normalize_tokens(query)
    findings, data_used = suggest_filters(df, logical_types, tokens)
    summary = (
        "Sugerencias de filtro para la barra lateral (no se aplican automáticamente). "
        "Los filtros activos solo afectan Exploración y Gráficos."
    )
    return _finalize(
        "filter",
        "Sugerencias de filtro",
        summary,
        findings,
        data_used,
        profile,
        query,
        extra_explanation="Los filtros deben configurarse manualmente en la barra lateral.",
    )


def _handle_unknown(profile: DatasetProfile, query: str) -> ConversationalResult:
    findings = [
        "Podés preguntar por: resumen del dataset, explicación de columnas, nulos, anomalías, "
        "comparaciones entre segmentos o sugerencias de filtro.",
        "Ejemplos: «Analizar este dataset», «¿Qué columnas tienen nulos?», «Detectar anomalías».",
    ]
    return _finalize(
        "unknown",
        "No reconocí la pregunta",
        "Reformulá la consulta usando palabras como resumen, explicar, nulos, anomalías o comparar.",
        findings,
        [],
        profile,
        query,
    )


def run_conversational_analysis(
    query: str,
    df: pd.DataFrame,
    logical_types: dict[str, str],
    profile: DatasetProfile,
    findings: list[Finding] | None = None,
) -> ConversationalResult:
    """
    Punto de entrada: clasifica intención y ejecuta el manejador correspondiente.
    Usa el dataframe completo cargado (no la vista filtrada).
    """
    q = (query or "").strip()
    if not q:
        return _empty_result(
            "unknown",
            "Pregunta vacía",
            "Escribí una pregunta o elegí un ejemplo.",
        )

    if df is None or df.shape[0] == 0:
        return _empty_result(
            "unknown",
            "Sin datos",
            "Cargá un dataset antes de hacer preguntas.",
        )

    quality_findings = findings if findings is not None else []
    intent = classify_intent(q)

    if intent == "summarize":
        return _handle_summarize(df, profile, logical_types, quality_findings, q)
    if intent == "explain":
        return _handle_explain(profile, logical_types, q)
    if intent == "detect_anomaly":
        return _handle_detect_anomaly(df, profile, logical_types, q)
    if intent == "search":
        return _handle_search(q, df, profile, logical_types)
    if intent == "compare":
        return _handle_compare(df, profile, logical_types, q)
    if intent == "filter":
        return _handle_filter(df, profile, logical_types, q)
    return _handle_unknown(profile, q)
