"""
Entrena no-show sobre data/synthetic_v2/ (pipeline paralelo; no modifica v1).

Uso:
  python scripts/train_no_show_v2.py --dataset-id signal_moderate_seed42 --seed 42
  python scripts/train_no_show_v2.py --all-scenarios --seed 42
"""

from __future__ import annotations

import argparse
import json
import logging
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
from paradigm.ml_v2.dataset import DEFAULT_SYNTHETIC_V2_ROOT  # noqa: E402
from paradigm.ml_v2.features import (  # noqa: E402
    FORBIDDEN_FEATURE_COLUMNS,
    PREDECISIONAL_CATEGORICAL,
    PREDECISIONAL_NUMERIC,
)
from paradigm.ml_v2.train import SELECTED_MODEL, run_training_v2  # noqa: E402

LOGGER = logging.getLogger(__name__)

_TEST_RATIO = 0.2
_DEFAULT_SEED = 42
_SCENARIO_DATASET_IDS = (
    "signal_weak_seed42",
    "signal_moderate_seed42",
    "signal_strong_seed42",
)

_MODEL_HYPERPARAMS = {
    "baseline_logistic": {
        "solver": "lbfgs",
        "class_weight": "balanced",
        "max_iter": 2000,
    },
    "random_forest": {
        "n_estimators": 120,
        "max_depth": 10,
        "min_samples_leaf": 5,
        "class_weight": "balanced",
        "n_jobs": -1,
    },
}


def build_config(dataset_id: str, seed: int) -> ExperimentConfig:
    return ExperimentConfig(
        experiment_type="classification",
        name=f"no_show_v2_{dataset_id}",
        question=(
            "Sobre synthetic_v2 con señal conocida, ¿un modelo con features "
            "predecisionales recupera ranking útil de no-show?"
        ),
        hypothesis=(
            "Con señal moderada/fuerte el ROC-AUC del modelo seleccionado se acerca "
            "al AUC de true_p (referencia) y supera al escenario débil."
        ),
        dataset=f"data/synthetic_v2/{dataset_id}/fact_appointment.csv",
        target="target_no_show",
        baseline="logistic_regression_baseline",
        seed=seed,
        params={
            "pipeline": "no_show_v2",
            "dataset_id": dataset_id,
            "test_ratio": _TEST_RATIO,
            "split": "temporal_by_appointment_date",
            "models_evaluated": ["baseline_logistic", "random_forest"],
            "selected_model": SELECTED_MODEL,
            "model_hyperparameters": _MODEL_HYPERPARAMS,
            "features_categorical": PREDECISIONAL_CATEGORICAL,
            "features_numeric": PREDECISIONAL_NUMERIC,
            "excluded_features": list(FORBIDDEN_FEATURE_COLUMNS),
        },
        notes=(
            "Parallel v2 pipeline on synthetic_v2. Does not write v1 legacy "
            "ml/experiments/metrics.json or mart-backed artifacts."
        ),
    )


def _build_report(run: ExperimentRun, summary: dict[str, Any]) -> str:
    metrics = summary.get("metrics", {})
    lr = metrics.get("baseline_logistic", {})
    rf = metrics.get("random_forest", {})
    ref = summary.get("true_p_reference", {})

    def _fmt(block: dict[str, Any], key: str) -> str:
        val = block.get(key)
        return f"{val:.4f}" if isinstance(val, (int, float)) else "N/A"

    return f"""# Experimento — {run.config.name}

| Campo | Valor |
|-------|-------|
| run_id | `{run.run_id}` |
| dataset_id | `{summary.get("dataset_id")}` |
| seed | {run.config.seed} |
| selected_model | `{SELECTED_MODEL}` |
| status | {run.metadata.status} |
| cutoff | `{summary.get("temporal_cutoff_appointment_date")}` |
| n_train / n_test | {summary.get("n_train")} / {summary.get("n_test")} |

## Features
- Categóricas: {", ".join(f"`{c}`" for c in PREDECISIONAL_CATEGORICAL)}
- Numéricas: {", ".join(f"`{c}`" for c in PREDECISIONAL_NUMERIC)}
- Excluidas (truth / latentes / post-outcome): ver `params.excluded_features`

## Métricas hold-out

| Modelo | ROC-AUC | PR-AUC | Brier | Log loss | Precision | Recall | F1 | Top-decile capture |
|--------|---------|--------|-------|----------|-----------|--------|----|--------------------|
| Logistic | {_fmt(lr, "roc_auc")} | {_fmt(lr, "pr_auc")} | {_fmt(lr, "brier")} | {_fmt(lr, "log_loss")} | {_fmt(lr, "precision")} | {_fmt(lr, "recall")} | {_fmt(lr, "f1")} | {(lr.get("top_decile") or {}).get("capture_rate")} |
| Random Forest (selected) | {_fmt(rf, "roc_auc")} | {_fmt(rf, "pr_auc")} | {_fmt(rf, "brier")} | {_fmt(rf, "log_loss")} | {_fmt(rf, "precision")} | {_fmt(rf, "recall")} | {_fmt(rf, "f1")} | {(rf.get("top_decile") or {}).get("capture_rate")} |

### Referencia generadora
- AUC(`true_p`): {_fmt(ref, "roc_auc")} (no es métrica de modelo entrenado)

## Artefactos
- Run: `{run.run_dir.as_posix()}`
"""


def run_no_show_v2_pipeline(
    *,
    dataset_id: str,
    seed: int = _DEFAULT_SEED,
    runs_dir: Path | None = None,
    data_root: Path | None = None,
    test_ratio: float = _TEST_RATIO,
) -> tuple[ExperimentRun, dict[str, Any]]:
    """Entrena v2, registra run en ml.experiments y persiste artefactos bajo el run."""
    config = build_config(dataset_id, seed)
    runs_root = Path(runs_dir) if runs_dir is not None else default_runs_root()
    run = start_run(config, base_dir=runs_root)
    LOGGER.info("Started v2 run %s → %s", run.run_id, run.run_dir)

    try:
        # Artefactos de entrenamiento viven dentro del run (no tocan legacy v1).
        summary = run_training_v2(
            dataset_id=dataset_id,
            out_dir=run.run_dir,
            data_root=data_root,
            test_ratio=test_ratio,
            seed=seed,
        )
        metrics_payload = {
            "models": summary.get("metrics", {}),
            "true_p_reference": summary.get("true_p_reference", {}),
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
            "dataset_id": dataset_id,
            "features_categorical": summary.get("features_categorical"),
            "features_numeric": summary.get("features_numeric"),
            "excluded_from_features": summary.get("excluded_from_features"),
            "claim_namespace": {
                "predictive_performance": summary.get("metrics", {}),
                "interpretation": None,
                "causality": None,
                "simulated_impact": None,
                "recommended_decision": {
                    "framing": "prioritization_ranking_synthetic_v2",
                    "selected_model": SELECTED_MODEL,
                },
            },
        }
        save_metrics(run, metrics_payload, merge=False)
        run.metadata.artifacts.update(
            {
                "predictions": "predictions/test_predictions.csv",
                "model_baseline_logistic": "models/no_show_logistic.joblib",
                "model_selected": "models/no_show_random_forest.joblib",
                "training_summary": "training_summary.json",
            }
        )
        finish_run(run, status="completed")
        (run.run_dir / "report.md").write_text(
            _build_report(run, summary),
            encoding="utf-8",
        )
        LOGGER.info("Finished v2 run %s", run.run_id)
        return run, summary
    except Exception as exc:
        LOGGER.exception("No-show v2 failed: %s", exc)
        if run.metadata.status not in ("completed", "failed", "discarded"):
            finish_run(run, status="failed", error=str(exc))
            (run.run_dir / "report.md").write_text(
                f"# Experimento — {run.config.name}\n\n**status:** `failed`\n\n`{exc}`\n",
                encoding="utf-8",
            )
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train no-show models on synthetic_v2 (parallel pipeline).")
    p.add_argument("--dataset-id", type=str, default=None, help="e.g. signal_moderate_seed42")
    p.add_argument(
        "--all-scenarios",
        action="store_true",
        help="Run weak/moderate/strong seed42 dataset ids",
    )
    p.add_argument("--seed", type=int, default=_DEFAULT_SEED)
    p.add_argument("--runs-dir", type=Path, default=None, help="Experiment runs root")
    p.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help=f"Root of synthetic_v2 datasets (default: {DEFAULT_SYNTHETIC_V2_ROOT})",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    args = parse_args(argv)
    if args.all_scenarios:
        dataset_ids = list(_SCENARIO_DATASET_IDS)
    elif args.dataset_id:
        dataset_ids = [args.dataset_id]
    else:
        print("Indicate --dataset-id or --all-scenarios", file=sys.stderr)
        return 2

    results: list[dict[str, Any]] = []
    for dataset_id in dataset_ids:
        run, summary = run_no_show_v2_pipeline(
            dataset_id=dataset_id,
            seed=args.seed,
            runs_dir=args.runs_dir,
            data_root=args.data_root,
        )
        rf = summary["metrics"]["random_forest"]
        results.append(
            {
                "dataset_id": dataset_id,
                "run_id": run.run_id,
                "run_dir": str(run.run_dir),
                "roc_auc": rf.get("roc_auc"),
                "pr_auc": rf.get("pr_auc"),
                "true_p_auc": (summary.get("true_p_reference") or {}).get("roc_auc"),
                "selected_model": summary.get("selected_model"),
            }
        )
        print(json.dumps(results[-1], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
