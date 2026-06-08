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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python" / "src"))

from paradigm.io.paths import DB_PATH, ML_EXPERIMENTS_DIR  # noqa: E402
from paradigm.ml.train import run_training  # noqa: E402


def main() -> None:
    summary = run_training(db_path=DB_PATH, out_dir=ML_EXPERIMENTS_DIR, test_ratio=0.2)
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

    print(f"\nArtefactos modelos: {ML_EXPERIMENTS_DIR}")


if __name__ == "__main__":
    main()
