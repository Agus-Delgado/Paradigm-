"""
Entrena modelos de no-show (baseline logístico + Random Forest) con split temporal.

Requisitos:
    python scripts/build_sqlite_mart.py

Uso (desde la raíz del repo):
    python scripts/train_no_show.py

Salida (compatibilidad — rutas actuales):
    ml/experiments/no_show_*.joblib
    ml/experiments/metrics.json
    ml/experiments/no_show_test_predictions.csv
    data/processed/shap_bundle.joblib
    ml/figures/shap_summary_beeswarm.png

Salida adicional (infraestructura de runs):
    ml/experiments/runs/<run_id>/
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "python" / "src"))

from ml.experiments import (  # noqa: E402
    ExperimentConfig,
    ExperimentRun,
    finish_run,
    save_metrics,
    start_run,
)
from ml.experiments.store import default_runs_root  # noqa: E402
from paradigm.io.paths import (  # noqa: E402
    DB_PATH,
    ML_EXPERIMENTS_DIR,
    ML_FIGURES_DIR,
    SHAP_BUNDLE_PATH,
    SHAP_SUMMARY_PNG,
)
from paradigm.ml.train import run_training  # noqa: E402

LOGGER = logging.getLogger(__name__)

# Hyperparameters mirrored from paradigm.ml.train (do not diverge).
_TEST_RATIO = 0.2
_SEED = 42
_MODEL_HYPERPARAMS = {
    "baseline_logistic": {
        "solver": "lbfgs",
        "class_weight": "balanced",
        "max_iter": 2000,
        "random_state": _SEED,
    },
    "random_forest": {
        "n_estimators": 120,
        "max_depth": 10,
        "min_samples_leaf": 5,
        "class_weight": "balanced",
        "random_state": _SEED,
    },
}

SELECTED_MODEL = "random_forest"


def build_no_show_config() -> ExperimentConfig:
    """Typed config for the no-show prioritization classification experiment."""
    return ExperimentConfig(
        experiment_type="classification",
        name="no_show_rf_baseline",
        question=(
            "En el decision point post-reserva, ¿qué citas priorizar para contacto "
            "ante riesgo de no-show?"
        ),
        hypothesis=(
            "Un ranking con historial de proveedor/paciente y features de booking "
            "mejora la captura top-10% de no-shows vs azar sobre el hold-out temporal."
        ),
        dataset="paradigm_mart.fact_appointment (ATTENDED|NO_SHOW)",
        target="target_no_show",
        baseline="logistic_regression_baseline",
        seed=_SEED,
        params={
            "test_ratio": _TEST_RATIO,
            "split": "temporal_by_appointment_date",
            "models_evaluated": ["baseline_logistic", "random_forest"],
            "selected_model": SELECTED_MODEL,
            "model_hyperparameters": _MODEL_HYPERPARAMS,
            "legacy_out_dir": str(ML_EXPERIMENTS_DIR),
        },
        notes=(
            "Temporal split training run for no-show prioritization. "
            "Methodology-first; synthetic AUC may be near/below 0.5."
        ),
    )


def _copy_if_exists(src: Path, dest: Path) -> Path | None:
    if not src.is_file():
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def _stage_run_artifacts(run: ExperimentRun, summary: dict[str, Any], out_dir: Path) -> None:
    """Copy legacy artifacts into the run layout (predictions/models/plots)."""
    pred_src = Path(summary.get("predictions_path") or (out_dir / "no_show_test_predictions.csv"))
    pred_dest = _copy_if_exists(pred_src, run.predictions_dir() / "test_predictions.csv")
    if pred_dest is not None:
        run.metadata.artifacts["predictions"] = "predictions/test_predictions.csv"

    logistic_dest = _copy_if_exists(
        out_dir / "no_show_logistic.joblib",
        run.models_dir() / "no_show_logistic.joblib",
    )
    rf_dest = _copy_if_exists(
        out_dir / "no_show_random_forest.joblib",
        run.models_dir() / "no_show_random_forest.joblib",
    )
    if logistic_dest is not None:
        run.metadata.artifacts["model_baseline_logistic"] = "models/no_show_logistic.joblib"
    if rf_dest is not None:
        run.metadata.artifacts["model_selected"] = "models/no_show_random_forest.joblib"

    plot_dest = _copy_if_exists(
        Path(summary.get("shap", {}).get("summary_png") or SHAP_SUMMARY_PNG),
        run.plots_dir() / "shap_summary_beeswarm.png",
    )
    if plot_dest is not None:
        run.metadata.artifacts["plot_shap_summary"] = "plots/shap_summary_beeswarm.png"

    shap_bundle = summary.get("shap", {}).get("bundle_path") or SHAP_BUNDLE_PATH
    bundle_dest = _copy_if_exists(Path(shap_bundle), run.models_dir() / "shap_bundle.joblib")
    if bundle_dest is not None:
        run.metadata.artifacts["shap_bundle"] = "models/shap_bundle.joblib"

    legacy_metrics = out_dir / "metrics.json"
    if legacy_metrics.is_file():
        _copy_if_exists(legacy_metrics, run.run_dir / "legacy_metrics.json")
        run.metadata.artifacts["legacy_metrics"] = "legacy_metrics.json"


def _build_experiment_report(run: ExperimentRun, summary: dict[str, Any]) -> str:
    """Markdown report combining run metadata with no-show methodology narrative."""
    metrics = summary.get("metrics", {})
    lr = metrics.get("baseline_logistic", {})
    rf = metrics.get("random_forest", {})
    impact = summary.get("business_impact_top10pct", {})
    shap = summary.get("shap", {})

    def _auc(block: dict[str, Any]) -> str:
        val = block.get("roc_auc")
        return f"{val:.4f}" if isinstance(val, (int, float)) else "N/A"

    shap_rows = shap.get("shap_importance_top") or rf.get("shap_importance_top") or []
    shap_lines = "\n".join(
        f"- `{row.get('feature')}`: {float(row.get('mean_abs_shap', 0)):.4f}"
        for row in shap_rows[:10]
    ) or "_SHAP no disponible._"

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
| selected_model | `{SELECTED_MODEL}` |

## 1. Pregunta e hipótesis
- Pregunta: {run.config.question}
- Hipótesis: {run.config.hypothesis}

## 2. Dataset, target y split
- Dataset: `{run.config.dataset}`
- Target: `{run.config.target}`
- Baseline: `{run.config.baseline}`
- Split: temporal por `appointment_date` (test_ratio={summary.get("test_ratio_target")})
- Cutoff: `{summary.get("temporal_cutoff_appointment_date")}`
- n_train / n_test: {summary.get("n_train")} / {summary.get("n_test")}

## 10. Métricas (hold-out)

| Modelo | ROC-AUC | AP | Brier | Accuracy | Top-decile capture |
|--------|---------|----|-------|----------|--------------------|
| Logistic (baseline) | {_auc(lr)} | {lr.get("average_precision")} | {lr.get("brier")} | {lr.get("accuracy")} | {(lr.get("top_decile") or {}).get("capture_rate")} |
| Random Forest (selected) | {_auc(rf)} | {rf.get("average_precision")} | {rf.get("brier")} | {rf.get("accuracy")} | {(rf.get("top_decile") or {}).get("capture_rate")} |

### Impacto operativo ilustrativo (top 10%, RF)
- Citas priorizadas: {impact.get("appointments_prioritized")}
- Slots liberados est.: {impact.get("slots_liberated_est")}
- Ingreso recuperado ARS: {impact.get("revenue_recovered_ars")}

## Interpretación (SHAP — asociación, no causalidad)
{shap_lines}

## 16. Limitaciones
- Datos sintéticos; AUC cerca o por debajo de 0.5 es una limitación documentada, no un bug.
- Impacto de negocio es simulado/ilustrativo.
- Este run no implica promoción a producción.

## 17. Artefactos
- Legacy: `ml/experiments/metrics.json`, `no_show_*.joblib`, predicciones CSV, SHAP bundle/PNG
- Run: `{run.run_dir.as_posix()}`

## 18. Decisión Learn
- **status:** `{run.metadata.status}`
"""


def run_no_show_pipeline(
    *,
    db_path: Path = DB_PATH,
    out_dir: Path = ML_EXPERIMENTS_DIR,
    runs_dir: Path | None = None,
    test_ratio: float = _TEST_RATIO,
    seed: int = _SEED,
) -> tuple[ExperimentRun, dict[str, Any]]:
    """Train no-show models, keep legacy artifact paths, and register a Learn-layer run.

    Parameters
    ----------
    db_path:
        SQLite mart path.
    out_dir:
        Legacy artifact directory (``ml/experiments`` by default).
    runs_dir:
        Parent for new runs (default ``ml/experiments/runs``). Pass a temp dir in tests.
    """
    config = build_no_show_config()
    # Keep seed/params aligned with call-site overrides without changing train defaults.
    config.seed = seed
    config.params["test_ratio"] = test_ratio
    config.params["legacy_out_dir"] = str(out_dir)

    runs_root = Path(runs_dir) if runs_dir is not None else default_runs_root()
    run = start_run(config, base_dir=runs_root)
    LOGGER.info("Started run %s → %s", run.run_id, run.run_dir)

    try:
        LOGGER.info("Running training pipeline (legacy out_dir=%s)...", out_dir)
        summary = run_training(
            db_path=db_path,
            out_dir=out_dir,
            test_ratio=test_ratio,
            random_state=seed,
        )

        metrics_payload = {
            "models": summary.get("metrics", {}),
            "split": {
                "strategy": "temporal_by_appointment_date",
                "test_ratio_target": summary.get("test_ratio_target"),
                "temporal_cutoff_appointment_date": summary.get(
                    "temporal_cutoff_appointment_date"
                ),
                "n_train": summary.get("n_train"),
                "n_test": summary.get("n_test"),
                "n_positive_train": summary.get("n_positive_train"),
                "n_positive_test": summary.get("n_positive_test"),
                "train_date_min": summary.get("train_date_min"),
                "train_date_max": summary.get("train_date_max"),
                "test_date_min": summary.get("test_date_min"),
                "test_date_max": summary.get("test_date_max"),
            },
            "selected_model": summary.get("selected_model", SELECTED_MODEL),
            "business_impact_top10pct": summary.get("business_impact_top10pct", {}),
            "claim_namespace": {
                "predictive_performance": summary.get("metrics", {}),
                "interpretation": {
                    "shap_available": bool(summary.get("shap", {}).get("shap_available")),
                    "shap_importance_top": summary.get("shap", {}).get("shap_importance_top"),
                },
                "simulated_impact": summary.get("business_impact_top10pct", {}),
                "causality": None,
                "recommended_decision": {
                    "framing": "prioritization_ranking",
                    "selected_model": summary.get("selected_model", SELECTED_MODEL),
                },
            },
        }
        save_metrics(run, metrics_payload, merge=False)
        _stage_run_artifacts(run, summary, out_dir)
        finish_run(run, status="completed")
        (run.run_dir / "report.md").write_text(
            _build_experiment_report(run, summary),
            encoding="utf-8",
        )
        LOGGER.info("Finished run %s as completed", run.run_id)
        return run, summary
    except Exception as exc:
        LOGGER.exception("No-show training failed: %s", exc)
        if run.metadata.status not in ("completed", "failed", "discarded"):
            finish_run(run, status="failed", error=str(exc))
            (run.run_dir / "report.md").write_text(
                f"# Experimento — {run.config.name}\n\n"
                f"**status:** `failed`\n\n## Error\n\n`{exc}`\n",
                encoding="utf-8",
            )
        raise


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    run, summary = run_no_show_pipeline()

    print(f"Run ID: {run.run_id}")
    print(f"Run dir: {run.run_dir}")
    print(json.dumps(summary["metrics"], indent=2, ensure_ascii=False))

    shap_info = summary.get("shap", {})
    if shap_info.get("shap_available"):
        print("\n--- SHAP (top features, mean |SHAP|) ---")
        for row in shap_info.get("shap_importance_top", [])[:10]:
            print(f"  {row['feature']}: {row['mean_abs_shap']:.4f}")
        print(f"Bundle: {shap_info.get('bundle_path')}")
        print(f"Summary PNG: {shap_info.get('summary_png')}")
    else:
        print("\n[WARN] SHAP no disponible; revisá dependencias (shap, matplotlib).")

    impact = summary.get("business_impact_top10pct", {})
    if impact:
        print("\n--- Impacto negocio (top 10%) ---")
        print(f"  Citas priorizadas: {impact.get('appointments_prioritized')}")
        print(f"  Slots liberados est.: {impact.get('slots_liberated_est')}")
        print(f"  Ingreso recuperado ARS: {impact.get('revenue_recovered_ars', 0):,.0f}")

    print(f"\nArtefactos legacy: {ML_EXPERIMENTS_DIR}")
    print(f"Figuras: {ML_FIGURES_DIR}")


if __name__ == "__main__":
    main()
