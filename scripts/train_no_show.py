"""
Entrena modelos de no-show (baseline logístico + Random Forest) con split temporal.

Requisitos:
    python scripts/build_sqlite_mart.py

Uso (desde la raíz del repo):
    python scripts/train_no_show.py

Salida:
    ml/experiments/no_show_*.joblib
    ml/experiments/metrics.json
    data/processed/shap_bundle.joblib
    ml/figures/shap_summary_beeswarm.png
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "python" / "src"))

from ml.experiments.tracker import ExperimentTracker  # noqa: E402
from paradigm.io.paths import DB_PATH, ML_EXPERIMENTS_DIR  # noqa: E402
from paradigm.ml.train import run_training  # noqa: E402


LOGGER = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    tracker = ExperimentTracker(base_dir=ML_EXPERIMENTS_DIR)
    experiment_id = tracker.start_experiment(
        name="no_show_rf_baseline",
        hyperparameters={
            "test_ratio": 0.2,
            "models": {
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
                },
            },
        },
        notes="Temporal split training run for no-show prioritization baseline.",
    )
    LOGGER.info("Started experiment %s", experiment_id)

    LOGGER.info("Running training pipeline...")
    summary = run_training(db_path=DB_PATH, out_dir=ML_EXPERIMENTS_DIR, test_ratio=0.2)
    tracker.log_metrics(summary.get("metrics", {}))
    LOGGER.info("Logged metrics for experiment %s", experiment_id)

    logistic_path = ML_EXPERIMENTS_DIR / "no_show_logistic.joblib"
    rf_path = ML_EXPERIMENTS_DIR / "no_show_random_forest.joblib"
    if logistic_path.exists():
        tracker.log_model(joblib.load(logistic_path), filename="no_show_logistic.joblib")
    if rf_path.exists():
        tracker.log_model(joblib.load(rf_path), filename="no_show_random_forest.joblib")
    LOGGER.info("Logged model artifacts for experiment %s", experiment_id)

    shap_info = summary.get("shap", {})
    shap_bundle_path = shap_info.get("bundle_path")
    if shap_info.get("shap_available") and shap_bundle_path:
        tracker.log_shap(joblib.load(Path(shap_bundle_path)))
        LOGGER.info("Logged SHAP bundle for experiment %s", experiment_id)

    tracker.finish_experiment()
    LOGGER.info("Finished experiment %s", experiment_id)

    print(f"Experiment ID: {experiment_id}")
    print(json.dumps(summary["metrics"], indent=2, ensure_ascii=False))

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

    print(f"\nArtefactos modelos: {ML_EXPERIMENTS_DIR}")


if __name__ == "__main__":
    main()
