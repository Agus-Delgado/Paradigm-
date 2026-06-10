"""Generación dinámica de preguntas guiadas según dominio y schema."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.conversational.dataset_snapshot import (
    DatasetSnapshot,
    build_dataset_snapshot,
    build_hypothesis_example,
    build_segment_hint,
)
from app.conversational.types import Domain, GuidedQuestion, QuestionPhase

_OBJECTIVE = GuidedQuestion(
    id="objective",
    label="¿Cuál es el objetivo principal o la pregunta de negocio que querés responder con estos datos?",
    hint="Ej.: reducir no-shows, explicar desvíos presupuestarios, identificar la planta con más defectos.",
    widget="text",
    default="",
)


def _wizard_for_domain(domain: Domain, snapshot: DatasetSnapshot) -> list[GuidedQuestion]:
    segments = snapshot.segment_columns or ("— sin segmentos —",)
    default_seg = segments[0]
    hypothesis_hint = build_hypothesis_example(domain, snapshot)
    segment_hint = build_segment_hint(snapshot, default_seg, domain)

    labels = {
        "healthcare_clinic": (
            "¿Qué métrica te preocupa más y por qué creés que está ocurriendo?",
            "¿Qué segmento o factor sospechás que es la raíz del problema?",
        ),
        "healthcare_mart": (
            "¿Qué señal operativa está fallando y cuál es tu hipótesis de causa raíz?",
            "¿Qué segmento o factor querés investigar primero?",
        ),
        "finance": (
            "¿Qué desvío financiero te preocupa y por qué creés que está ocurriendo?",
            "¿Qué segmento o factor sospechás que concentra el desvío?",
        ),
        "operations": (
            "¿Qué KPI operativo está fuera de objetivo y por qué creés que ocurre?",
            "¿Qué planta, línea o turno sospechás que concentra el problema?",
        ),
        "generic": (
            "¿Qué métrica te preocupa y por qué creés que está ocurriendo?",
            "¿Qué segmento o factor sospechás que es la raíz del problema?",
        ),
    }
    hyp_label, seg_label = labels[domain]

    return [
        _OBJECTIVE,
        GuidedQuestion(
            id="hypothesis",
            label=hyp_label,
            hint=hypothesis_hint,
            widget="text",
            default="",
        ),
        GuidedQuestion(
            id="segment_col",
            label=seg_label,
            hint=segment_hint,
            widget="select",
            options=segments,
            default=default_seg,
        ),
    ]


def generate_guided_questions(
    df: pd.DataFrame,
    logical_types: dict[str, str],
    domain: Domain,
    phase: QuestionPhase = "wizard",
    profile: Any = None,
    findings: list | None = None,
) -> list[GuidedQuestion]:
    """Wizard: máx. 3 preguntas orientadas a objetivo e hipótesis de causa raíz."""
    if phase != "wizard":
        return []

    snapshot = build_dataset_snapshot(df, logical_types, profile, domain, findings)
    return _wizard_for_domain(domain, snapshot)[:3]
