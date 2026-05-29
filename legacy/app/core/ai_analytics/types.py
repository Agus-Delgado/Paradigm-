"""Tipos para la capa conversacional determinística (v1)."""

from __future__ import annotations

from typing import Literal, TypedDict

Intent = Literal[
    "summarize",
    "compare",
    "filter",
    "detect_anomaly",
    "explain",
    "search",
    "unknown",
]

Confidence = Literal["low", "medium", "high"]


class ConversationalResult(TypedDict):
    intent: Intent
    title: str
    summary: str
    findings: list[str]
    data_used: list[str]
    confidence: Confidence
    explanation: str
    suggested_next_step: str
