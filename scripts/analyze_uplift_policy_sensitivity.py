"""
Sensibilidad risk vs uplift vs net_value (capacidad, costos, calidad uplift).

No modifica modelos ni generador.

Uso:
  python scripts/analyze_uplift_policy_sensitivity.py
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "python" / "src"))

from paradigm.io.paths import REPO_ROOT  # noqa: E402
from paradigm.ml_v2.uplift_policy_sensitivity import run_multiseed_sensitivity  # noqa: E402

DEFAULT_DATASETS = (
    "policy_intervention_seed41",
    "policy_intervention_seed42",
    "policy_intervention_seed43",
)


def _json_safe(obj: Any) -> Any:
    import numpy as np

    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return v if not (math.isnan(v) or math.isinf(v)) else None
    return obj


def find_uplift_run(runs_root: Path, dataset_id: str) -> Path:
    matches = sorted(runs_root.glob(f"*uplift_v2_{dataset_id}"))
    if not matches:
        raise FileNotFoundError(f"No hay run uplift para {dataset_id} bajo {runs_root}")
    return matches[-1]


def load_preds(run_dir: Path):
    import pandas as pd

    path = run_dir / "predictions" / "test_uplift_predictions.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Uplift policy sensitivity (multiseed)")
    p.add_argument("--runs-dir", type=Path, default=REPO_ROOT / "ml" / "experiments" / "runs")
    p.add_argument(
        "--json-out",
        type=Path,
        default=REPO_ROOT / "ml" / "experiments" / "uplift_v2_policy_sensitivity.json",
    )
    p.add_argument("--datasets", nargs="*", default=list(DEFAULT_DATASETS))
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    preds_by_seed: dict[str, Any] = {}
    meta: dict[str, str] = {}
    for dataset_id in args.datasets:
        run_dir = find_uplift_run(args.runs_dir, dataset_id)
        preds_by_seed[dataset_id] = load_preds(run_dir)
        meta[dataset_id] = str(run_dir)

    report = run_multiseed_sensitivity(preds_by_seed)
    report["run_dirs"] = meta

    # Compact table for defaults slice
    cells = report["aggregate"]["cells"]
    default_slice = [
        c
        for c in cells
        if c["benefit_per_avoided"] == 10.0
        and c["intervention_cost"] == 0.4
        and c["uplift_quality"] == 0.0
    ]
    quality_slice = [
        c
        for c in cells
        if c["capacity"] == 30
        and c["benefit_per_avoided"] == 10.0
        and c["intervention_cost"] == 0.4
    ]
    report["tables"] = {
        "capacity_at_B10_C0.4_q0": default_slice,
        "quality_at_cap30_B10_C0.4": quality_slice,
    }

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(_json_safe(report), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Wrote {args.json_out}")
    print(
        json.dumps(
            {
                "n_cells": report["aggregate"]["n_cells"],
                "stability_rate": report["aggregate"]["stability_rate"],
                "majority_win_frequency": report["aggregate"]["majority_win_frequency"],
                "n_frontiers": len(report["frontiers"]),
                "when_each_wins": {
                    k: v["n_cells"] for k, v in report["when_each_wins"].items()
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
