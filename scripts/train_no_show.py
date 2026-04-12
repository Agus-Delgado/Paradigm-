"""
Entrena modelos de no-show (baseline logístico + Random Forest) con split temporal.

Requisitos:
    python scripts/build_sqlite_mart.py

Uso (desde la raíz del repo):
    python scripts/train_no_show.py

Salida: ml/experiments/no_show_*.joblib y ml/experiments/metrics.json
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
    print(f"Artefactos: {ML_EXPERIMENTS_DIR}")


if __name__ == "__main__":
    main()
