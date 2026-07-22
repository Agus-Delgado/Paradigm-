"""Typed contract for Paradigm experiment runs (stdlib dataclasses)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ExperimentType = Literal[
    "classification",
    "regression",
    "forecasting",
    "clustering",
    "causality",
    "simulation",
    "prescriptive_policy",
]

RunStatus = Literal["running", "completed", "failed", "discarded"]

EXPERIMENT_TYPES: tuple[str, ...] = (
    "classification",
    "regression",
    "forecasting",
    "clustering",
    "causality",
    "simulation",
    "prescriptive_policy",
)

TERMINAL_STATUSES: tuple[str, ...] = ("completed", "failed", "discarded")


@dataclass
class ExperimentConfig:
    """Declarative configuration for a single experiment run.

    Fields map to the Learn-layer contract in ``docs/EXPERIMENT_STANDARD.md``.
    Extra hyperparameters may live in ``params`` without polluting the core schema.
    """

    experiment_type: ExperimentType
    name: str
    question: str
    hypothesis: str
    dataset: str
    target: str
    baseline: str
    seed: int = 42
    params: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    parent_run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentConfig:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        payload = {k: v for k, v in data.items() if k in known}
        return cls(**payload)


@dataclass
class ExperimentMetadata:
    """Runtime metadata persisted in ``metadata.json`` for one run."""

    run_id: str
    status: RunStatus
    experiment_type: ExperimentType
    name: str
    question: str
    hypothesis: str
    dataset: str
    target: str
    baseline: str
    seed: int
    started_at_utc: str
    finished_at_utc: str | None = None
    duration_seconds: float | None = None
    python_version: str = ""
    git_commit: str | None = None
    error: str | None = None
    notes: str = ""
    parent_run_id: str | None = None
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentMetadata:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        payload = {k: v for k, v in data.items() if k in known}
        return cls(**payload)
