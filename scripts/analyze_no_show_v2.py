"""
Análisis de error/calibración de runs no-show v2.

No modifica features, modelos ni hiperparámetros; reutiliza predicciones o reentrena
solo para estabilidad multi-seed con la misma config.

Uso:
  python scripts/analyze_no_show_v2.py
  python scripts/analyze_no_show_v2.py --seeds 1,2,3,4,5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "python" / "src"))

from paradigm.io.paths import REPO_ROOT  # noqa: E402
from paradigm.ml_v2.dataset import DEFAULT_SYNTHETIC_V2_ROOT, load_eligible_v2  # noqa: E402
from paradigm.ml_v2.error_analysis import (  # noqa: E402
    analyze_predictions,
    load_run_predictions,
    multi_seed_stability,
    save_calibration_plot,
)
from paradigm.ml_v2.train import run_training_v2  # noqa: E402

SCENARIOS = (
    ("signal_weak", "signal_weak_seed42"),
    ("signal_moderate", "signal_moderate_seed42"),
    ("signal_strong", "signal_strong_seed42"),
)


def _json_safe(obj: Any) -> Any:
    import math

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


def find_run_dir(runs_root: Path, dataset_id: str) -> Path | None:
    matches = sorted(runs_root.glob(f"*no_show_v2_{dataset_id}"))
    return matches[-1] if matches else None


def ensure_predictions(
    dataset_id: str,
    *,
    runs_root: Path,
    data_root: Path,
    seed: int,
) -> tuple[Path, Any]:
    run_dir = find_run_dir(runs_root, dataset_id)
    if run_dir is not None and (run_dir / "predictions" / "test_predictions.csv").is_file():
        return run_dir, load_run_predictions(run_dir)
    # Fallback: train once into runs_root (same hyperparams; does not change v1)
    from scripts.train_no_show_v2 import run_no_show_v2_pipeline

    run, _ = run_no_show_v2_pipeline(
        dataset_id=dataset_id,
        seed=seed,
        runs_dir=runs_root,
        data_root=data_root,
    )
    return run.run_dir, load_run_predictions(run.run_dir)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Error/calibration analysis for no-show v2")
    p.add_argument("--runs-dir", type=Path, default=REPO_ROOT / "ml" / "experiments" / "runs")
    p.add_argument("--data-root", type=Path, default=DEFAULT_SYNTHETIC_V2_ROOT)
    p.add_argument("--seed", type=int, default=42, help="Seed of the baseline runs to analyze")
    p.add_argument(
        "--seeds",
        type=str,
        default="1,2,3,4,5",
        help="Comma-separated seeds for stability (retrain, same hyperparams)",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "ml" / "figures" / "no_show_v2_error",
    )
    p.add_argument(
        "--json-out",
        type=Path,
        default=REPO_ROOT / "ml" / "experiments" / "no_show_v2_error_analysis.json",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    seeds = [int(x.strip()) for x in args.seeds.split(",") if x.strip()]
    args.out_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "seed_baseline": args.seed,
        "stability_seeds": seeds,
        "scenarios": {},
    }

    for scenario, dataset_id in SCENARIOS:
        run_dir, preds = ensure_predictions(
            dataset_id,
            runs_root=args.runs_dir,
            data_root=args.data_root,
            seed=args.seed,
        )
        appts = load_eligible_v2(dataset_id, data_root=args.data_root)
        analysis = analyze_predictions(preds, appts)
        analysis["dataset_id"] = dataset_id
        analysis["run_dir"] = str(run_dir)

        plot_paths = {}
        for model_name, model_block in analysis["models"].items():
            path = save_calibration_plot(
                model_block,
                title=f"{scenario} — {model_name}",
                out_path=args.out_dir / f"calibration_{scenario}_{model_name}.png",
            )
            if path is not None:
                plot_paths[model_name] = str(path)
        analysis["calibration_plots"] = plot_paths

        stability = multi_seed_stability(
            dataset_id,
            seeds,
            data_root=args.data_root,
        )
        analysis["stability"] = stability
        report["scenarios"][scenario] = analysis
        print(
            f"{scenario}: n_test={analysis['n_test']} "
            f"better_cal={analysis['comparison']['better_calibrated']} "
            f"better_auc={analysis['comparison']['better_ranking_auc']}"
        )

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(_json_safe(report), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.json_out}")
    print(f"Plots under {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
