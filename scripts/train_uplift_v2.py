"""
Entrena uplift Two-Model sobre policy_intervention (synthetic_v2).

Uso:
  python scripts/train_uplift_v2.py --dataset-id policy_intervention_seed42 --seed 42
  python scripts/train_uplift_v2.py --all-seeds
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
from paradigm.ml_v2.uplift_train import (  # noqa: E402
    TREATMENT_COLUMN,
    UPLIFT_SELECTED_MODEL,
    run_uplift_training_v2,
)

LOGGER = logging.getLogger(__name__)

_TEST_RATIO = 0.2
_DEFAULT_SEED = 42
_DEFAULT_DATASETS = (
    "policy_intervention_seed41",
    "policy_intervention_seed42",
    "policy_intervention_seed43",
)

_MODEL_HYPERPARAMS = {
    "logistic_regression": {
        "solver": "lbfgs",
        "class_weight": "balanced",
        "max_iter": 2000,
        "note": "two pipelines: control + treated",
    },
    "random_forest": {
        "n_estimators": 120,
        "max_depth": 10,
        "min_samples_leaf": 5,
        "class_weight": "balanced",
        "n_jobs": -1,
        "note": "two pipelines: control + treated",
    },
}


def build_config(dataset_id: str, seed: int) -> ExperimentConfig:
    return ExperimentConfig(
        experiment_type="causality",
        name=f"uplift_v2_{dataset_id}",
        question=(
            "Sobre policy_intervention, ¿un Two-Model (LR/RF) recupera ranking "
            "de beneficio individual del recordatorio adicional?"
        ),
        hypothesis=(
            "El uplift p̂0−p̂1 ordena mejor que azar (Qini>0) y concentra "
            "segmentos de alto efecto (WEB, lead largo)."
        ),
        dataset=f"data/synthetic_v2/{dataset_id}/fact_appointment.csv",
        target="uplift_score = P(Y|X,T=0) - P(Y|X,T=1)",
        baseline="random_treatment_same_fraction",
        seed=seed,
        params={
            "pipeline": "uplift_v2_two_model",
            "approach": "two_model",
            "dataset_id": dataset_id,
            "treatment_column": TREATMENT_COLUMN,
            "test_ratio": _TEST_RATIO,
            "split": "temporal_by_appointment_date",
            "models_evaluated": ["logistic_regression", "random_forest"],
            "default_selected_model": UPLIFT_SELECTED_MODEL,
            "selection_rule": "max_qini_coefficient_on_holdout",
            "model_hyperparameters": _MODEL_HYPERPARAMS,
            "features_categorical": PREDECISIONAL_CATEGORICAL,
            "features_numeric": PREDECISIONAL_NUMERIC,
            "excluded_features": list(FORBIDDEN_FEATURE_COLUMNS),
            "cost_policy_connected": False,
        },
        notes=(
            "Uplift Two-Model on synthetic intervention. Truth only for evaluation. "
            "Not wired to cost/threshold policy."
        ),
    )


def _fmt_qini(block: dict[str, Any]) -> str:
    q = (block.get("qini") or {}).get("qini_coefficient")
    return f"{q:.4f}" if isinstance(q, (int, float)) else "N/A"


def _fmt_spearman(block: dict[str, Any]) -> str:
    s = block.get("spearman_vs_true_benefit")
    return f"{s:.4f}" if isinstance(s, (int, float)) else "N/A"


def _policy_at(block: dict[str, Any], fraction: float) -> str:
    rows = (block.get("policy_value") or {}).get("model") or []
    for r in rows:
        if abs(float(r.get("fraction", -1)) - fraction) < 1e-9:
            v = r.get("mean_true_benefit")
            lift = r.get("lift_vs_random")
            if isinstance(v, (int, float)) and isinstance(lift, (int, float)):
                return f"{v:.4f} (Δrand {lift:+.4f})"
    return "N/A"


def _build_report(run: ExperimentRun, summary: dict[str, Any]) -> str:
    metrics = summary.get("metrics", {})
    lr = metrics.get("logistic_regression", {})
    rf = metrics.get("random_forest", {})
    selected = summary.get("selected_model", UPLIFT_SELECTED_MODEL)
    seg = (metrics.get(selected) or {}).get("segment_recovery_top20") or {}

    return f"""# Experimento — {run.config.name}

| Campo | Valor |
|-------|-------|
| run_id | `{run.run_id}` |
| dataset_id | `{summary.get("dataset_id")}` |
| seed | {run.config.seed} |
| approach | Two-Model |
| selected_model | `{selected}` |
| status | {run.metadata.status} |
| cutoff | `{summary.get("temporal_cutoff_appointment_date")}` |
| n_train / n_test | {summary.get("n_train")} / {summary.get("n_test")} |
| train treated / control | {summary.get("n_train_treated")} / {summary.get("n_train_control")} |

## Definición
- Tratamiento: `{TREATMENT_COLUMN}` (recordatorio adicional)
- Score: `uplift = p̂(Y=1∣X,T=0) − p̂(Y=1∣X,T=1)`
- Truth solo evaluación (`true_ite_probability`); **no** features
- **No** conectado a política de costos

## Métricas hold-out

| Modelo | Qini | Spearman(score, true_benefit) | Policy value @20% |
|--------|------|-------------------------------|-------------------|
| Logistic | {_fmt_qini(lr)} | {_fmt_spearman(lr)} | {_policy_at(lr, 0.2)} |
| Random Forest | {_fmt_qini(rf)} | {_fmt_spearman(rf)} | {_policy_at(rf, 0.2)} |

## Segment recovery (selected, top 20%)
- Base rates: `{json.dumps(seg.get("base_rates", {}), ensure_ascii=False)}`
- Top rates: `{json.dumps(seg.get("top_rates", {}), ensure_ascii=False)}`
- Rate lift: `{json.dumps(seg.get("rate_lift", {}), ensure_ascii=False)}`
- recovers_priority_segments: `{seg.get("recovers_priority_segments")}`

## Artefactos
- Run: `{run.run_dir.as_posix()}`
"""


def run_uplift_v2_pipeline(
    *,
    dataset_id: str,
    seed: int = _DEFAULT_SEED,
    runs_dir: Path | None = None,
    data_root: Path | None = None,
    test_ratio: float = _TEST_RATIO,
) -> tuple[ExperimentRun, dict[str, Any]]:
    config = build_config(dataset_id, seed)
    runs_root = Path(runs_dir) if runs_dir is not None else default_runs_root()
    run = start_run(config, base_dir=runs_root)
    LOGGER.info("Started uplift run %s → %s", run.run_id, run.run_dir)

    try:
        summary = run_uplift_training_v2(
            dataset_id=dataset_id,
            out_dir=run.run_dir,
            data_root=data_root,
            test_ratio=test_ratio,
            seed=seed,
        )
        metrics_payload = {
            "approach": "two_model",
            "models": summary.get("metrics", {}),
            "selected_model": summary.get("selected_model"),
            "selection_rule": summary.get("selection_rule"),
            "split": {
                "strategy": "temporal_by_appointment_date",
                "test_ratio_target": summary.get("test_ratio_target"),
                "temporal_cutoff_appointment_date": summary.get(
                    "temporal_cutoff_appointment_date"
                ),
                "n_train": summary.get("n_train"),
                "n_test": summary.get("n_test"),
                "n_train_treated": summary.get("n_train_treated"),
                "n_train_control": summary.get("n_train_control"),
                "train_date_min": summary.get("train_date_min"),
                "train_date_max": summary.get("train_date_max"),
                "test_date_min": summary.get("test_date_min"),
                "test_date_max": summary.get("test_date_max"),
            },
            "dataset_id": dataset_id,
            "treatment_column": TREATMENT_COLUMN,
            "uplift_definition": summary.get("uplift_definition"),
            "features_categorical": summary.get("features_categorical"),
            "features_numeric": summary.get("features_numeric"),
            "excluded_from_features": summary.get("excluded_from_features"),
            "cost_policy_connected": False,
            "claim_namespace": {
                "predictive_performance": None,
                "causality": {
                    "method": "two_model_uplift",
                    "selected_model": summary.get("selected_model"),
                    "qini": (summary.get("metrics") or {})
                    .get(summary.get("selected_model"), {})
                    .get("qini"),
                },
                "simulated_impact": {
                    "policy_value": (summary.get("metrics") or {})
                    .get(summary.get("selected_model"), {})
                    .get("policy_value"),
                    "baselines": ["random", "treat_all", "treat_none"],
                },
                "recommended_decision": None,
            },
        }
        save_metrics(run, metrics_payload, merge=False)
        run.metadata.artifacts.update(
            {
                "predictions": "predictions/test_uplift_predictions.csv",
                "model_logistic_control": "models/uplift_logistic_control.joblib",
                "model_logistic_treated": "models/uplift_logistic_treated.joblib",
                "model_rf_control": "models/uplift_rf_control.joblib",
                "model_rf_treated": "models/uplift_rf_treated.joblib",
                "training_summary": "uplift_training_summary.json",
            }
        )
        finish_run(run, status="completed")
        (run.run_dir / "report.md").write_text(
            _build_report(run, summary),
            encoding="utf-8",
        )
        LOGGER.info("Finished uplift run %s", run.run_id)
        return run, summary
    except Exception as exc:
        LOGGER.exception("Uplift v2 failed: %s", exc)
        if run.metadata.status not in ("completed", "failed", "discarded"):
            finish_run(run, status="failed", error=str(exc))
            (run.run_dir / "report.md").write_text(
                f"# Experimento — {run.config.name}\n\n**status:** `failed`\n\n`{exc}`\n",
                encoding="utf-8",
            )
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train Two-Model uplift on policy_intervention.")
    p.add_argument("--dataset-id", type=str, default=None)
    p.add_argument(
        "--all-seeds",
        action="store_true",
        help="Run policy_intervention seeds 41/42/43",
    )
    p.add_argument("--seed", type=int, default=_DEFAULT_SEED)
    p.add_argument("--runs-dir", type=Path, default=None)
    p.add_argument("--data-root", type=Path, default=None)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    args = parse_args(argv)
    if args.all_seeds:
        dataset_ids = list(_DEFAULT_DATASETS)
    elif args.dataset_id:
        dataset_ids = [args.dataset_id]
    else:
        print("Indicate --dataset-id or --all-seeds", file=sys.stderr)
        return 2

    results: list[dict[str, Any]] = []
    for dataset_id in dataset_ids:
        # Seed del modelo alineado al número del dataset si es policy_intervention_seedN
        seed = args.seed
        if dataset_id.startswith("policy_intervention_seed"):
            try:
                seed = int(dataset_id.rsplit("seed", 1)[-1])
            except ValueError:
                seed = args.seed
        run, summary = run_uplift_v2_pipeline(
            dataset_id=dataset_id,
            seed=seed,
            runs_dir=args.runs_dir,
            data_root=args.data_root,
        )
        selected = summary["selected_model"]
        block = summary["metrics"][selected]
        results.append(
            {
                "dataset_id": dataset_id,
                "run_id": run.run_id,
                "run_dir": str(run.run_dir),
                "selected_model": selected,
                "qini_coefficient": (block.get("qini") or {}).get("qini_coefficient"),
                "spearman_vs_true_benefit": block.get("spearman_vs_true_benefit"),
                "policy_value_top20": next(
                    (
                        r.get("mean_true_benefit")
                        for r in ((block.get("policy_value") or {}).get("model") or [])
                        if abs(float(r.get("fraction", -1)) - 0.2) < 1e-9
                    ),
                    None,
                ),
                "segment_recovery": (block.get("segment_recovery_top20") or {}).get(
                    "recovers_priority_segments"
                ),
            }
        )
        print(json.dumps(results[-1], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
