"""Experiment run registry for the Paradigm decision lab.

New runs live under ``ml/experiments/runs/<run_id>/``.
The legacy ``ExperimentTracker`` in ``tracker.py`` remains unchanged and is
**not** migrated by this package — existing training scripts keep working.
"""

from __future__ import annotations

from ml.experiments.contract import (
    EXPERIMENT_TYPES,
    TERMINAL_STATUSES,
    ExperimentConfig,
    ExperimentMetadata,
    ExperimentType,
    RunStatus,
)
from ml.experiments.run_id import generate_run_id, slugify
from ml.experiments.runner import (
    ExperimentRun,
    finish_run,
    load_run,
    resolve_git_commit,
    save_metrics,
    start_run,
)
from ml.experiments.store import OPTIONAL_SUBDIRS, REQUIRED_FILES, default_runs_root

__all__ = [
    "EXPERIMENT_TYPES",
    "OPTIONAL_SUBDIRS",
    "REQUIRED_FILES",
    "TERMINAL_STATUSES",
    "ExperimentConfig",
    "ExperimentMetadata",
    "ExperimentRun",
    "ExperimentType",
    "RunStatus",
    "default_runs_root",
    "finish_run",
    "generate_run_id",
    "load_run",
    "resolve_git_commit",
    "save_metrics",
    "slugify",
    "start_run",
]
