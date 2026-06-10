"""Construye el plan de análisis a partir de las respuestas del usuario."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.conversational.dataset_snapshot import DatasetSnapshot, build_dataset_snapshot
from app.conversational.types import AnalysisPlan, Domain


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _resolve_col(value: str | None) -> str | None:
    if not value or value.startswith("—"):
        return None
    return value


def build_analysis_plan(
    answers: dict[str, str | float],
    domain: Domain,
    logical_types: dict[str, str],
    df: pd.DataFrame | None = None,
    profile: Any = None,
    findings: list | None = None,
    snapshot: DatasetSnapshot | None = None,
) -> AnalysisPlan:
    objective = _clean_text(str(answers.get("objective", ""))) or "Explorar el dataset y detectar oportunidades"
    hypothesis = _clean_text(str(answers.get("hypothesis", "")))
    metric_col = _resolve_col(str(answers.get("metric_col", "")))
    segment_col = _resolve_col(str(answers.get("segment_col", "")))

    snap = snapshot
    if snap is None and df is not None:
        snap = build_dataset_snapshot(df, logical_types, profile, domain, findings)

    if snap:
        if not metric_col and snap.metric_columns:
            metric_col = snap.metric_columns[0]
        if not segment_col and snap.segment_columns and not snap.segment_columns[0].startswith("—"):
            segment_col = snap.segment_columns[0]
        if not metric_col and snap.outlier_columns:
            metric_col = snap.outlier_columns[0]

    if domain == "healthcare_clinic" and not metric_col:
        if "ingreso_neto" in logical_types:
            metric_col = "ingreso_neto"
    elif domain == "finance" and not metric_col:
        for candidate in ("variacion_pct", "real", "presupuesto"):
            if candidate in logical_types:
                metric_col = candidate
                break
    elif domain == "operations" and not metric_col:
        for candidate in ("defectos", "tasa_defecto_pct", "tiempo_ciclo_min", "unidades"):
            if candidate in logical_types:
                metric_col = candidate
                break

    if domain == "healthcare_mart" and not segment_col:
        segment_col = "specialty_name"
    elif domain == "operations" and not segment_col and "planta" in logical_types:
        segment_col = "planta"

    threshold_raw = answers.get("outlier_threshold_pct")
    threshold: float | None = None
    if threshold_raw is not None and str(threshold_raw).strip():
        try:
            threshold = float(threshold_raw)
        except (TypeError, ValueError):
            threshold = 10.0

    focus = _clean_text(str(answers.get("focus_area", "")))
    if hypothesis and not focus:
        lower = hypothesis.lower()
        if any(k in lower for k in ("no-show", "no show", "ausent", "ausencia")):
            focus = "Tasa de no-shows / ausencias"
        elif any(k in lower for k in ("defecto", "calidad", "scrap")):
            focus = "Defectos y calidad"
        elif any(k in lower for k in ("presupuesto", "desvío", "desvio", "costo", "financ")):
            focus = "Desvío financiero"

    return AnalysisPlan(
        objective=objective,
        domain=domain,
        metric_col=metric_col,
        segment_col=segment_col,
        focus_area=focus,
        outlier_threshold_pct=threshold,
        priority_criterion=_clean_text(str(answers.get("priority_criterion", ""))),
        hypothesis=hypothesis,
    )
