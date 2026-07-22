"""
Análisis de política de decisión uplift × costos (seeds policy_intervention).

No modifica modelos ni hiperparámetros.

Uso:
  python scripts/analyze_uplift_v2_policy.py
  python scripts/analyze_uplift_v2_policy.py --capacity 30 --capacity-fraction 0.2
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
from paradigm.ml_v2.uplift_decision_policy import (  # noqa: E402
    UpliftPolicyCostConfig,
    analyze_uplift_decision_policy,
)

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


def load_uplift_predictions(run_dir: Path):
    import pandas as pd

    path = run_dir / "predictions" / "test_uplift_predictions.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Uplift × cost decision policy analysis")
    p.add_argument("--runs-dir", type=Path, default=REPO_ROOT / "ml" / "experiments" / "runs")
    p.add_argument("--benefit", type=float, default=10.0)
    p.add_argument("--intervention-cost", type=float, default=0.4)
    p.add_argument("--capacity", type=int, default=30)
    p.add_argument("--capacity-fraction", type=float, default=0.2)
    p.add_argument("--min-net-value", type=float, default=0.0)
    p.add_argument(
        "--json-out",
        type=Path,
        default=REPO_ROOT / "ml" / "experiments" / "uplift_v2_decision_policy.json",
    )
    p.add_argument(
        "--datasets",
        nargs="*",
        default=list(DEFAULT_DATASETS),
        help="dataset ids (default: seeds 41/42/43)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = UpliftPolicyCostConfig(
        benefit_per_avoided=args.benefit,
        intervention_cost=args.intervention_cost,
        max_interventions=args.capacity,
        max_intervention_fraction=args.capacity_fraction,
        min_net_value=args.min_net_value,
    )
    report: dict[str, Any] = {"config": config.to_dict(), "seeds": {}}
    wins: dict[str, int] = {}

    for dataset_id in args.datasets:
        run_dir = find_uplift_run(args.runs_dir, dataset_id)
        preds = load_uplift_predictions(run_dir)
        block = analyze_uplift_decision_policy(preds, config)
        block["dataset_id"] = dataset_id
        block["run_dir"] = str(run_dir)
        report["seeds"][dataset_id] = block
        w = block["winner"]
        wins[w] = wins.get(w, 0) + 1
        wm = block["winner_metrics"]
        print(
            json.dumps(
                {
                    "dataset_id": dataset_id,
                    "model": block.get("model_name"),
                    "winner": w,
                    "capacity": block.get("resolved_capacity"),
                    "n_intervened": wm.get("n_intervened"),
                    "true_net_value": wm.get("true_net_value"),
                    "vs_treat_all": block.get("improvement_vs_treat_all"),
                    "vs_risk": block.get("improvement_vs_risk"),
                },
                indent=2,
                ensure_ascii=False,
            )
        )

    # Agregado: media de true_net por política
    policy_nets: dict[str, list[float]] = {}
    for block in report["seeds"].values():
        for name, row in (block.get("policies") or {}).items():
            tn = row.get("true_net_value")
            if tn is not None:
                policy_nets.setdefault(name, []).append(float(tn))
    aggregate = {
        name: {
            "mean_true_net_value": float(np_mean(vals)),
            "n_seeds": len(vals),
        }
        for name, vals in policy_nets.items()
    }
    from paradigm.ml_v2.uplift_decision_policy import CAPACITY_BOUND_POLICIES

    constrained_means = {
        k: v for k, v in aggregate.items() if k in CAPACITY_BOUND_POLICIES
    }
    best_constrained = (
        max(constrained_means.items(), key=lambda kv: kv[1]["mean_true_net_value"])[0]
        if constrained_means
        else None
    )
    report["aggregate"] = {
        "wins_by_policy_capacity_bound": wins,
        "mean_true_net_by_policy": aggregate,
        "recommended_policy_capacity_bound": best_constrained,
        "treat_all_unconstrained_mean_net": (aggregate.get("treat_all") or {}).get(
            "mean_true_net_value"
        ),
        "note": (
            "Ganador operativo = mejor true_net entre políticas con capacidad. "
            "treat_all se reporta sin tope como referencia de rentabilidad media."
        ),
    }

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(_json_safe(report), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote {args.json_out}")
    print(json.dumps(report["aggregate"], indent=2, ensure_ascii=False))
    return 0


def np_mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
