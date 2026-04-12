"""Resultado de un check de calidad."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass(frozen=True)
class CheckResult:
    """Una fila del reporte de calidad."""

    check_id: str
    name: str
    severity: Severity
    detail: str
    metric_value: int | float | None = None
