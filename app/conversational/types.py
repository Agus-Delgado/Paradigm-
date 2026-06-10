"""Tipos para el flujo de analista conversacional."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import pandas as pd

Domain = Literal["healthcare_clinic", "healthcare_mart", "finance", "operations", "generic"]
ImpactLevel = Literal["Alto", "Medio", "Bajo"]
WidgetKind = Literal["text", "select", "number"]
QuestionPhase = Literal["wizard", "deep"]


@dataclass(frozen=True)
class GuidedQuestion:
    id: str
    label: str
    hint: str
    widget: WidgetKind
    options: tuple[str, ...] = ()
    default: str | float | None = None
    required: bool = True


@dataclass
class AnalysisPlan:
    objective: str
    domain: Domain
    metric_col: str | None = None
    segment_col: str | None = None
    focus_area: str | None = None
    outlier_threshold_pct: float | None = None
    priority_criterion: str | None = None
    hypothesis: str | None = None


@dataclass
class ScoredRecommendation:
    impact: ImpactLevel
    text: str


@dataclass
class ContextualAnalysisResult:
    title: str
    summary: str
    findings: list[str]
    recommendations: list[ScoredRecommendation]
    data_used: list[str]
    domain_label: str


@dataclass
class DatasetContext:
    df: pd.DataFrame
    logical_types: dict[str, str]
    profile: Any
    findings: list[Any]
    domain: Domain
    dataset_key: str
    source_label: str
