"""Filesystem helpers for experiment run directories (no I/O on import)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_FILES = ("config.json", "metadata.json", "metrics.json", "report.md")
OPTIONAL_SUBDIRS = ("predictions", "plots", "models")


def default_runs_root() -> Path:
    """Canonical root for new runs: ``ml/experiments/runs``."""
    return Path(__file__).resolve().parent / "runs"


def ensure_run_layout(run_dir: Path, *, create_optional_subdirs: bool = True) -> Path:
    """Create the run directory with required files and optional subdirs.

    Does not overwrite existing non-empty files; creates empty stubs if missing.
    """
    run_dir.mkdir(parents=True, exist_ok=False)

    for filename in REQUIRED_FILES:
        path = run_dir / filename
        if filename.endswith(".json"):
            path.write_text("{}\n", encoding="utf-8")
        else:
            path.write_text("", encoding="utf-8")

    if create_optional_subdirs:
        for name in OPTIONAL_SUBDIRS:
            (run_dir / name).mkdir(parents=True, exist_ok=True)

    return run_dir


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_stub_report(
    *,
    run_id: str,
    experiment_type: str,
    name: str,
    question: str,
    hypothesis: str,
    dataset: str,
    target: str,
    baseline: str,
    seed: int,
    status: str,
    git_commit: str | None,
) -> str:
    """Minimal Markdown report aligned with ``docs/EXPERIMENT_STANDARD.md``."""
    commit = git_commit or "N/A"
    return f"""# Experimento — {name}

| Campo | Valor |
|-------|-------|
| run_id | `{run_id}` |
| experiment_type | {experiment_type} |
| status | {status} |
| git_commit | `{commit}` |
| seed | {seed} |

## 1. Pregunta e hipótesis
- Pregunta: {question}
- Hipótesis: {hypothesis}

## 2. Dataset y target
- Dataset: `{dataset}`
- Target: `{target}`
- Baseline: `{baseline}`

## 10. Métricas
_Pendiente — usar `save_metrics(...)` y volver a finalizar el run._

## 16. Limitaciones
- Run registrado con la infraestructura mínima de `ml/experiments`.
- No implica promoción a producción ni claim causal.

## 17. Artefactos
| Archivo | Path relativo |
|---------|---------------|
| config | `config.json` |
| metadata | `metadata.json` |
| metrics | `metrics.json` |
| report | `report.md` |
| predictions/ | opcional |
| plots/ | opcional |
| models/ | opcional |

## 18. Decisión Learn
- **status:** `{status}`
"""
