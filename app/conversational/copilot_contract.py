"""Contrato tipado de Paradigm Copilot.

No ejecuta codigo. Las correcciones son propuestas y toda salida requiere revision humana.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CopilotTask(str, Enum):
    """Tareas soportadas por el contrato, sin ejecutar codigo ni llamar motores externos."""

    EXPLAIN_SQL = "EXPLAIN_SQL"
    REVIEW_SQL = "REVIEW_SQL"
    EXPLAIN_PYTHON = "EXPLAIN_PYTHON"
    ANALYZE_ERROR = "ANALYZE_ERROR"
    PROPOSE_FIX = "PROPOSE_FIX"


@dataclass(frozen=True)
class CopilotRequest:
    """Solicitud tipada. Conserva el contenido recibido y no ejecuta codigo."""

    task: CopilotTask
    content: str
    context: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        content = self.content.strip()
        context = self.context.strip() if self.context is not None else None
        error_message = self.error_message.strip() if self.error_message is not None else None

        if not content:
            raise ValueError("content no puede estar vacio")
        if self.task is CopilotTask.ANALYZE_ERROR and not error_message:
            raise ValueError("ANALYZE_ERROR requiere error_message")

        object.__setattr__(self, "content", content)
        object.__setattr__(self, "context", context or None)
        object.__setattr__(self, "error_message", error_message or None)


@dataclass(frozen=True)
class CopilotResponse:
    """Respuesta tipada. Las correcciones son propuestas y requieren revision humana."""

    summary: str
    explanation: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    suggested_fix: str | None = None
    risks: list[str] = field(default_factory=list)
    requires_review: bool = True


def build_response_payload(response: CopilotResponse) -> dict[str, Any]:
    """Devuelve un payload serializable, estable y sin ejecutar codigo."""

    return {
        "summary": response.summary,
        "explanation": list(response.explanation),
        "issues": list(response.issues),
        "suggested_fix": response.suggested_fix,
        "risks": list(response.risks),
        "requires_review": response.requires_review,
    }