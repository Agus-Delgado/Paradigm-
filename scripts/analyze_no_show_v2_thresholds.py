"""
Análisis de umbral de decisión (costos + capacidad) para no-show v2.

Solo moderate/strong. No modifica modelos ni features.

Uso:
  python scripts/analyze_no_show_v2_thresholds.py
  python scripts/analyze_no_show_v2_thresholds.py --cost-fp 1 --cost-fn 8 --benefit 12 --capacity 25
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
from paradigm.ml_v2.dataset import DEFAULT_SYNTHETIC_V2_ROOT  # noqa: E402
from paradigm.ml_v2.error_analysis import load_run_predictions  # noqa: E402
from paradigm.ml_v2.threshold_policy import (  # noqa: E402
    ThresholdCostConfig,
    analyze_predictions_thresholds,
)

SCENARIOS = (
    ("signal_moderate", "signal_moderate_seed42"),
    ("signal_strong", "signal_strong_seed42"),
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


def find_run_dir(runs_root: Path, dataset_id: str) -> Path:
    matches = sorted(runs_root.glob(f"*no_show_v2_{dataset_id}"))
    if not matches:
        raise FileNotFoundError(f"No hay run para {dataset_id} bajo {runs_root}")
    return matches[-1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Threshold policy analysis for no-show v2")
    p.add_argument("--runs-dir", type=Path, default=REPO_ROOT / "ml" / "experiments" / "runs")
    p.add_argument("--cost-fp", type=float, default=1.0)
    p.add_argument("--cost-fn", type=float, default=5.0)
    p.add_argument("--benefit", type=float, default=10.0, help="Benefit per avoided no-show")
    p.add_argument("--capacity", type=int, default=30, help="Max interventions on hold-out")
    p.add_argument(
        "--capacity-fraction",
        type=float,
        default=None,
        help="Optional fraction of hold-out (combined with --capacity via min)",
    )
    p.add_argument(
        "--json-out",
        type=Path,
        default=REPO_ROOT / "ml" / "experiments" / "no_show_v2_threshold_analysis.json",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = ThresholdCostConfig(
        cost_fp=args.cost_fp,
        cost_fn=args.cost_fn,
        benefit_per_avoided=args.benefit,
        max_interventions=args.capacity,
        max_intervention_fraction=args.capacity_fraction,
    )
    report: dict[str, Any] = {"config": config.to_dict(), "scenarios": {}}
    for scenario, dataset_id in SCENARIOS:
        run_dir = find_run_dir(args.runs_dir, dataset_id)
        preds = load_run_predictions(run_dir)
        block = analyze_predictions_thresholds(preds, config)
        block["dataset_id"] = dataset_id
        block["run_dir"] = str(run_dir)
        report["scenarios"][scenario] = block
        for model, rec in block["recommendations"].items():
            print(
                f"{scenario} | {model}: thr={rec['threshold']:.3f} "
                f"n={rec['n_intervened']} net={rec['net_value']:.1f} "
                f"P={rec['precision']:.3f} R={rec['recall']:.3f}"
            )
        print(f"  best_by_net={block['best_model_by_net_value']}")

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(_json_safe(report), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
