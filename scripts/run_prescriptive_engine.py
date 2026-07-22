"""
Ejecuta el motor prescriptivo unificado sobre predicciones no-show v2.

Uso:
  python scripts/run_prescriptive_engine.py
  python scripts/run_prescriptive_engine.py --scenarios moderate strong
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "python" / "src"))

from ml.experiments import ExperimentConfig, finish_run, save_metrics, start_run  # noqa: E402
from ml.experiments.store import default_runs_root  # noqa: E402
from paradigm.prescriptive import PrescriptiveConfig, run_prescriptive_engine  # noqa: E402

LOGGER = logging.getLogger(__name__)

SCENARIO_DATASETS = {
    "moderate": "signal_moderate_seed42",
    "strong": "signal_strong_seed42",
}


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


def find_risk_predictions(runs_root: Path, dataset_id: str) -> Path:
    matches = sorted(runs_root.glob(f"*no_show_v2_{dataset_id}"))
    if not matches:
        raise FileNotFoundError(f"No risk run for {dataset_id} under {runs_root}")
    path = matches[-1] / "predictions" / "test_predictions.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Unified prescriptive engine (no UI)")
    p.add_argument("--scenarios", nargs="*", default=["moderate", "strong"])
    p.add_argument("--runs-dir", type=Path, default=None)
    p.add_argument("--benefit", type=float, default=10.0)
    p.add_argument("--intervention-cost", type=float, default=0.4)
    p.add_argument("--capacity", type=int, default=30)
    p.add_argument("--capacity-fraction", type=float, default=0.2)
    p.add_argument("--uplift-quality", type=float, default=0.0)
    p.add_argument(
        "--json-out",
        type=Path,
        default=ROOT / "ml" / "experiments" / "prescriptive_engine_report.json",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    args = parse_args(argv)
    runs_root = Path(args.runs_dir) if args.runs_dir else default_runs_root()
    cfg = PrescriptiveConfig(
        benefit_per_avoided=args.benefit,
        intervention_cost=args.intervention_cost,
        max_interventions=args.capacity,
        max_intervention_fraction=args.capacity_fraction,
        uplift_quality=args.uplift_quality,
    )

    report: dict[str, Any] = {"config": cfg.to_dict(), "scenarios": {}}

    for scenario in args.scenarios:
        dataset_id = SCENARIO_DATASETS.get(scenario, scenario)
        pred_path = find_risk_predictions(runs_root, dataset_id)
        preds = pd.read_csv(pred_path)
        LOGGER.info("%s: loaded %s rows from %s", scenario, len(preds), pred_path)

        result = run_prescriptive_engine(preds, cfg)

        exp = ExperimentConfig(
            experiment_type="prescriptive_policy",
            name=f"prescriptive_engine_{dataset_id}",
            question="¿A quién intervenir bajo capacidad con la regla risk/uplift/none?",
            hypothesis="Con uplift_quality=0 el motor aplica risk si C < B*ATE; none si no.",
            dataset=str(pred_path),
            target="recommended_action",
            baseline="none",
            seed=cfg.random_seed,
            params={
                "pipeline": "prescriptive_engine_v1",
                "policy_used": result.policy_used,
                "connected_to_ui": False,
            },
            notes="Unified Decide engine. Not wired to UI/chat.",
        )
        run = start_run(exp, base_dir=runs_root)
        try:
            pred_dir = run.predictions_dir()
            pred_dir.mkdir(parents=True, exist_ok=True)
            # Flatten uncertainty for CSV
            rec = result.recommendations.copy()
            rec["uncertainty_json"] = rec["uncertainty"].apply(json.dumps)
            rec.drop(columns=["uncertainty"]).to_csv(
                pred_dir / "recommendations.csv", index=False
            )
            payload = {
                "scenario": scenario,
                "dataset_id": dataset_id,
                "source_predictions": str(pred_path),
                **result.to_dict(),
            }
            save_metrics(run, _json_safe(payload), merge=False)
            finish_run(run, status="completed")
            (run.run_dir / "report.md").write_text(
                _md(run.run_id, scenario, result),
                encoding="utf-8",
            )
            payload["run_id"] = run.run_id
            payload["run_dir"] = str(run.run_dir)
            report["scenarios"][scenario] = payload
            print(
                json.dumps(
                    _json_safe(
                        {
                            "scenario": scenario,
                            "policy_used": result.policy_used,
                            "n_intervened": result.n_intervened,
                            "capacity": result.capacity,
                            "reason": result.policy_selection.get("reason"),
                            "example": result.recommendations.head(1).to_dict(orient="records"),
                        }
                    ),
                    indent=2,
                    ensure_ascii=False,
                )
            )
        except Exception as exc:
            LOGGER.exception("Failed %s: %s", scenario, exc)
            if run.metadata.status not in ("completed", "failed", "discarded"):
                finish_run(run, status="failed", error=str(exc))
            raise

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(_json_safe(report), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote {args.json_out}")
    return 0


def _md(run_id: str, scenario: str, result) -> str:
    return f"""# Prescriptive engine — {scenario}

| Campo | Valor |
|-------|-------|
| run_id | `{run_id}` |
| policy_used | `{result.policy_used}` |
| n_intervened | {result.n_intervened} |
| capacity | {result.capacity} |
| reason | {result.policy_selection.get("reason")} |

Not connected to UI/chat.
"""


if __name__ == "__main__":
    raise SystemExit(main())
