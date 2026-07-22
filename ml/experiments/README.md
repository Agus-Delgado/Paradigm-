# Experiment run registry (Paradigm Learn layer)

Minimal, local filesystem registry aligned with [`docs/EXPERIMENT_STANDARD.md`](../../docs/EXPERIMENT_STANDARD.md).

- **New API:** `start_run` / `save_metrics` / `finish_run` → `ml/experiments/runs/<run_id>/`
- **Legacy:** `tracker.py` (`ExperimentTracker`) stays as-is for existing train scripts — **not migrated yet**.

## Quick start — no-show classification (integrated)

```bash
python scripts/build_sqlite_mart.py
python scripts/train_no_show.py
```

Writes **legacy** artifacts under `ml/experiments/` (`metrics.json`, `no_show_*.joblib`, predictions CSV)
and a structured run under `ml/experiments/runs/<run_id>/` via `ExperimentConfig` / `start_run`.

```python
from pathlib import Path
from scripts.train_no_show import run_no_show_pipeline

run, summary = run_no_show_pipeline(runs_dir=Path("/tmp/paradigm_runs"))
print(run.run_id, summary["metrics"]["random_forest"]["roc_auc"])
```

## Quick start — generic API

```python
from ml.experiments import ExperimentConfig, finish_run, save_metrics, start_run

config = ExperimentConfig(
    experiment_type="classification",
    name="demo_prioritization",
    question="¿Qué citas priorizar ante riesgo de no-show?",
    hypothesis="Un ranking con historial de proveedor mejora captura top-10% vs azar.",
    dataset="paradigm_mart.fact_appointment",
    target="target_no_show",
    baseline="positive_rate",
    seed=42,
)

run = start_run(config)  # creates ml/experiments/runs/<run_id>/
save_metrics(run, {"roc_auc": 0.42, "top_decile_capture": 0.09})
finish_run(run, status="completed")
print(run.run_id, run.run_dir)
```

Terminal statuses: `completed` | `failed` | `discarded`.

## Layout per run

```text
ml/experiments/runs/<YYYYMMDD_HHMMSS_slug>/
  config.json
  metadata.json
  metrics.json
  report.md
  predictions/   # optional
  plots/
  models/
```

## Notes

- Importing `ml.experiments` does **not** create directories or write files.
- Git commit is recorded when available; otherwise `git_commit` is `null`.
- No MLflow / W&B / database — stdlib + core deps only.
