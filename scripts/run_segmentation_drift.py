"""
Segmentación (KMeans) + monitoreo de drift por ventanas temporales.

No conecta segmentos a decisiones ni modifica modelos existentes.

Uso:
  python scripts/run_segmentation_drift.py
  python scripts/run_segmentation_drift.py --dataset-id signal_moderate_seed42
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
from paradigm.ml_v2.dataset import DEFAULT_SYNTHETIC_V2_ROOT, load_eligible_v2  # noqa: E402
from paradigm.ml_v2.features import (  # noqa: E402
    FORBIDDEN_FEATURE_COLUMNS,
    PREDECISIONAL_CATEGORICAL,
    PREDECISIONAL_NUMERIC,
)
from paradigm.monitoring.pipeline import run_segmentation_and_drift  # noqa: E402

LOGGER = logging.getLogger(__name__)


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
    if isinstance(obj, np.ndarray):
        return _json_safe(obj.tolist())
    return obj


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Segmentation + drift monitoring")
    p.add_argument("--dataset-id", default="signal_moderate_seed42")
    p.add_argument("--data-root", type=Path, default=None)
    p.add_argument("--k-max", type=int, default=5)
    p.add_argument("--n-windows", type=int, default=3)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--runs-dir", type=Path, default=None)
    p.add_argument(
        "--json-out",
        type=Path,
        default=ROOT / "ml" / "experiments" / "segmentation_drift_report.json",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    args = parse_args(argv)
    data_root = args.data_root or DEFAULT_SYNTHETIC_V2_ROOT
    df = load_eligible_v2(args.dataset_id, data_root=data_root)
    LOGGER.info("Loaded %s rows from %s", len(df), args.dataset_id)

    k_values = tuple(range(2, max(3, args.k_max) + 1))
    result = run_segmentation_and_drift(
        df,
        k_values=k_values,
        n_windows=args.n_windows,
        seed=args.seed,
    )

    config = ExperimentConfig(
        experiment_type="clustering",
        name=f"segmentation_drift_{args.dataset_id}",
        question=(
            "¿Qué segmentos predecisionales emergen y cómo derivan features/"
            "prevalencia entre ventanas temporales?"
        ),
        hypothesis=(
            "KMeans con K elegido por silhouette produce clusters medianamente "
            "estables (ARI≥0.7); drift aparece en lead_time / canal / prevalencia."
        ),
        dataset=f"data/synthetic_v2/{args.dataset_id}/fact_appointment.csv",
        target="cluster_label (unsupervised); prevalence monitored separately",
        baseline="k=2",
        seed=args.seed,
        params={
            "pipeline": "segmentation_and_drift_v1",
            "k_values": list(k_values),
            "best_k": result["best_k"],
            "n_windows": args.n_windows,
            "features_categorical": PREDECISIONAL_CATEGORICAL,
            "features_numeric": PREDECISIONAL_NUMERIC,
            "excluded_features": list(FORBIDDEN_FEATURE_COLUMNS),
            "connected_to_decisions": False,
        },
        notes="Compact segmentation + drift. Not wired to decisions.",
    )
    runs_root = Path(args.runs_dir) if args.runs_dir else default_runs_root()
    run = start_run(config, base_dir=runs_root)

    try:
        labels = pd.DataFrame(
            {
                "appointment_id": df["appointment_id"].to_numpy(),
                "appointment_date": pd.to_datetime(df["appointment_date"]).dt.strftime("%Y-%m-%d"),
                "cluster": result["labels"],
            }
        )
        pred_dir = run.predictions_dir()
        pred_dir.mkdir(parents=True, exist_ok=True)
        labels.to_csv(pred_dir / "cluster_assignments.csv", index=False)
        pd.DataFrame(result["profiles"]).to_csv(pred_dir / "segment_profiles.csv", index=False)
        pd.DataFrame(result["k_comparison"]).to_csv(pred_dir / "k_comparison.csv", index=False)

        # Persist drift without huge numeric dumps beyond top features
        metrics_payload = {
            "best_k": result["best_k"],
            "k_comparison": result["k_comparison"],
            "stability": result["stability"],
            "profiles": result["profiles"],
            "windows": result["windows"],
            "drift_by_window": result["drift_by_window"],
            "top_drift_alerts": result["top_drift_alerts"],
            "n": result["n"],
            "connected_to_decisions": False,
        }
        save_metrics(run, _json_safe(metrics_payload), merge=False)
        run.metadata.artifacts.update(
            {
                "cluster_assignments": "predictions/cluster_assignments.csv",
                "segment_profiles": "predictions/segment_profiles.csv",
                "k_comparison": "predictions/k_comparison.csv",
            }
        )
        finish_run(run, status="completed")
        (run.run_dir / "report.md").write_text(
            _report_md(run.run_id, result),
            encoding="utf-8",
        )

        out = {
            **metrics_payload,
            "run_id": run.run_id,
            "run_dir": str(run.run_dir),
            "dataset_id": args.dataset_id,
        }
        # Drop full label list from json out
        out.pop("labels", None)
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(_json_safe(out), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(
            json.dumps(
                _json_safe(
                    {
                        "run_id": run.run_id,
                        "best_k": result["best_k"],
                        "stability": result["stability"],
                        "profiles": result["profiles"],
                        "top_drift_alerts": result["top_drift_alerts"],
                        "windows": result["windows"],
                        "json_out": str(args.json_out),
                    }
                ),
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    except Exception as exc:
        LOGGER.exception("Segmentation/drift failed: %s", exc)
        if run.metadata.status not in ("completed", "failed", "discarded"):
            finish_run(run, status="failed", error=str(exc))
        raise


def _report_md(run_id: str, result: dict[str, Any]) -> str:
    stab = result.get("stability") or {}
    lines = [
        f"# Segmentation + drift — `{run_id}`",
        "",
        f"- best_k: **{result.get('best_k')}**",
        f"- mean_seed_ARI: **{stab.get('mean_seed_ari')}** (stable={stab.get('stable')})",
        f"- top_drift_alerts: `{result.get('top_drift_alerts')}`",
        "",
        "## Profiles",
    ]
    for p in result.get("profiles") or []:
        lines.append(
            f"- cluster {p.get('cluster')}: n={p.get('n')} share={p.get('share'):.2f} "
            f"lead={p.get('mean_lead_time_days')} noshow={p.get('prevalence_no_show')}"
        )
    lines.append("")
    lines.append("Not connected to decisions.")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
