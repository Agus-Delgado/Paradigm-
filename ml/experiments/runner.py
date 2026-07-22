"""Start, update, and finish experiment runs on the local filesystem."""

from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ml.experiments.contract import (
    TERMINAL_STATUSES,
    ExperimentConfig,
    ExperimentMetadata,
    RunStatus,
)
from ml.experiments.run_id import generate_run_id
from ml.experiments.store import (
    OPTIONAL_SUBDIRS,
    build_stub_report,
    default_runs_root,
    ensure_run_layout,
    read_json,
    write_json,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(moment: datetime | None = None) -> str:
    value = moment or _utc_now()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(iso_text: str) -> datetime:
    text = iso_text.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def resolve_git_commit() -> str | None:
    """Return HEAD commit hash when Git is available; otherwise ``None``."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        commit = result.stdout.strip()
        return commit or None
    except Exception:
        return None


@dataclass
class ExperimentRun:
    """In-memory handle for an active (or finished) experiment run."""

    run_id: str
    run_dir: Path
    config: ExperimentConfig
    metadata: ExperimentMetadata
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> RunStatus:
        return self.metadata.status

    def predictions_dir(self) -> Path:
        path = self.run_dir / "predictions"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def plots_dir(self) -> Path:
        path = self.run_dir / "plots"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def models_dir(self) -> Path:
        path = self.run_dir / "models"
        path.mkdir(parents=True, exist_ok=True)
        return path


def start_run(
    config: ExperimentConfig,
    *,
    base_dir: Path | None = None,
    run_id: str | None = None,
    create_optional_subdirs: bool = True,
    git_commit: str | None | object = ...,
) -> ExperimentRun:
    """Create a new run directory and persist initial config/metadata/report.

    Parameters
    ----------
    config:
        Typed experiment configuration.
    base_dir:
        Parent directory for runs (default: ``ml/experiments/runs``).
    run_id:
        Optional precomputed id; otherwise generated from UTC time + name.
    create_optional_subdirs:
        When True, creates empty ``predictions/``, ``plots/``, ``models/``.
    git_commit:
        Override Git commit. Pass ``None`` to force absence; omit to auto-detect.
    """
    if config.experiment_type not in (
        "classification",
        "regression",
        "forecasting",
        "clustering",
        "causality",
        "simulation",
        "prescriptive_policy",
    ):
        raise ValueError(f"Unsupported experiment_type: {config.experiment_type!r}")

    root = Path(base_dir) if base_dir is not None else default_runs_root()
    root.mkdir(parents=True, exist_ok=True)

    resolved_id = run_id or generate_run_id(config.name)
    run_dir = root / resolved_id
    if run_dir.exists():
        # Collision within the same second: append a short monotonic suffix.
        for index in range(1, 1000):
            candidate = f"{resolved_id}_{index:03d}"
            candidate_dir = root / candidate
            if not candidate_dir.exists():
                resolved_id = candidate
                run_dir = candidate_dir
                break
        else:
            raise FileExistsError(f"Unable to allocate unique run directory under {root}")

    ensure_run_layout(run_dir, create_optional_subdirs=create_optional_subdirs)

    if git_commit is ...:
        commit = resolve_git_commit()
    else:
        commit = git_commit  # type: ignore[assignment]

    started = _utc_iso()
    metadata = ExperimentMetadata(
        run_id=resolved_id,
        status="running",
        experiment_type=config.experiment_type,  # type: ignore[arg-type]
        name=config.name,
        question=config.question,
        hypothesis=config.hypothesis,
        dataset=config.dataset,
        target=config.target,
        baseline=config.baseline,
        seed=config.seed,
        started_at_utc=started,
        finished_at_utc=None,
        duration_seconds=None,
        python_version=platform.python_version(),
        git_commit=commit,
        error=None,
        notes=config.notes,
        parent_run_id=config.parent_run_id,
        artifacts={
            "config": "config.json",
            "metadata": "metadata.json",
            "metrics": "metrics.json",
            "report": "report.md",
            **{name: f"{name}/" for name in OPTIONAL_SUBDIRS if (run_dir / name).is_dir()},
        },
    )

    write_json(run_dir / "config.json", config.to_dict())
    write_json(run_dir / "metadata.json", metadata.to_dict())
    write_json(run_dir / "metrics.json", {})
    (run_dir / "report.md").write_text(
        build_stub_report(
            run_id=resolved_id,
            experiment_type=config.experiment_type,
            name=config.name,
            question=config.question,
            hypothesis=config.hypothesis,
            dataset=config.dataset,
            target=config.target,
            baseline=config.baseline,
            seed=config.seed,
            status=metadata.status,
            git_commit=commit,
        ),
        encoding="utf-8",
    )

    return ExperimentRun(
        run_id=resolved_id,
        run_dir=run_dir,
        config=config,
        metadata=metadata,
        metrics={},
    )


def save_metrics(run: ExperimentRun, metrics: dict[str, Any], *, merge: bool = True) -> Path:
    """Persist metrics to ``metrics.json`` (merge by default)."""
    if run.metadata.status in TERMINAL_STATUSES:
        raise RuntimeError(f"Cannot save metrics on a {run.metadata.status} run.")
    if not isinstance(metrics, dict):
        raise TypeError("metrics must be a dict")

    if merge:
        run.metrics.update(metrics)
    else:
        run.metrics = dict(metrics)

    path = run.run_dir / "metrics.json"
    write_json(path, run.metrics)
    return path


def finish_run(
    run: ExperimentRun,
    *,
    status: RunStatus = "completed",
    error: str | None = None,
    notes: str | None = None,
) -> Path:
    """Mark the run as terminal and refresh metadata + report."""
    if status not in TERMINAL_STATUSES:
        raise ValueError(
            f"status must be one of {TERMINAL_STATUSES}, got {status!r}"
        )
    if run.metadata.status in TERMINAL_STATUSES:
        raise RuntimeError(f"Run {run.run_id} already finished as {run.metadata.status}.")

    finished_at = _utc_iso()
    started_at = _parse_utc(run.metadata.started_at_utc)
    finished_dt = _parse_utc(finished_at)
    duration = max(0.0, (finished_dt - started_at).total_seconds())

    run.metadata.status = status
    run.metadata.finished_at_utc = finished_at
    run.metadata.duration_seconds = duration
    if error is not None:
        run.metadata.error = error
    elif status == "failed" and run.metadata.error is None:
        run.metadata.error = "Run finished with status=failed"
    if notes:
        existing = run.metadata.notes or ""
        run.metadata.notes = f"{existing}\n{notes}".strip() if existing else notes

    write_json(run.run_dir / "metadata.json", run.metadata.to_dict())
    write_json(run.run_dir / "metrics.json", run.metrics)

    (run.run_dir / "report.md").write_text(
        _render_final_report(run),
        encoding="utf-8",
    )
    return run.run_dir / "metadata.json"


def load_run(run_dir: Path) -> ExperimentRun:
    """Reload a run from disk (utility for tests and inspection)."""
    run_dir = Path(run_dir)
    config = ExperimentConfig.from_dict(read_json(run_dir / "config.json"))
    metadata = ExperimentMetadata.from_dict(read_json(run_dir / "metadata.json"))
    metrics = read_json(run_dir / "metrics.json")
    return ExperimentRun(
        run_id=metadata.run_id,
        run_dir=run_dir,
        config=config,
        metadata=metadata,
        metrics=metrics,
    )


def _render_final_report(run: ExperimentRun) -> str:
    metrics_lines = (
        "\n".join(f"- `{key}`: {value}" for key, value in sorted(run.metrics.items()))
        if run.metrics
        else "_Sin métricas registradas._"
    )
    error_block = f"\n## Error\n\n`{run.metadata.error}`\n" if run.metadata.error else ""
    return f"""# Experimento — {run.config.name}

| Campo | Valor |
|-------|-------|
| run_id | `{run.run_id}` |
| experiment_type | {run.config.experiment_type} |
| status | {run.metadata.status} |
| git_commit | `{run.metadata.git_commit or "N/A"}` |
| seed | {run.config.seed} |
| python_version | {run.metadata.python_version} |
| started_at_utc | {run.metadata.started_at_utc} |
| finished_at_utc | {run.metadata.finished_at_utc} |
| duration_seconds | {run.metadata.duration_seconds} |

## 1. Pregunta e hipótesis
- Pregunta: {run.config.question}
- Hipótesis: {run.config.hypothesis}

## 2. Dataset y target
- Dataset: `{run.config.dataset}`
- Target: `{run.config.target}`
- Baseline: `{run.config.baseline}`

## 10. Métricas
{metrics_lines}
{error_block}
## 16. Limitaciones
- Run registrado con la infraestructura mínima de `ml/experiments`.
- No implica promoción a producción ni claim causal.

## 18. Decisión Learn
- **status:** `{run.metadata.status}`
"""


__all__ = [
    "ExperimentRun",
    "finish_run",
    "load_run",
    "resolve_git_commit",
    "save_metrics",
    "start_run",
]
