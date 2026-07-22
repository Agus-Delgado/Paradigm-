"""
Benchmark reproducible de baselines de forecasting (sin conectar a decisiones).

Modelos: Naive, Seasonal Naive, Moving Average, Exponential Smoothing (si hay statsmodels).

Uso:
  python scripts/benchmark_forecast_baselines.py
  python scripts/benchmark_forecast_baselines.py --horizon 14 --step 7
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "python" / "src"))

from ml.experiments import ExperimentConfig, finish_run, save_metrics, start_run  # noqa: E402
from ml.experiments.store import default_runs_root  # noqa: E402
from ml.forecasting.evaluation import (  # noqa: E402
    PRIMARY_SELECTION_METRIC,
    select_best_model,
)
from ml.forecasting.models import (  # noqa: E402
    BENCHMARK_BASELINE_MODELS,
    exp_smoothing_available,
)
from ml.forecasting.trainer import train_and_evaluate_forecaster  # noqa: E402
from paradigm.io.paths import DB_PATH, REPO_ROOT  # noqa: E402
from scripts.train_forecast import (  # noqa: E402
    load_daily_series,
)

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
    return obj


def model_kwargs_for(name: str, season_length: int) -> dict[str, Any]:
    if name == "seasonal_naive":
        return {"season_length": season_length}
    if name == "moving_average":
        return {"window": season_length}
    if name == "exp_smoothing":
        return {"trend": "add", "seasonal": "add", "seasonal_periods": season_length}
    return {}


def resolve_benchmark_models() -> tuple[list[str], list[str]]:
    """Returns (runnable, skipped)."""
    runnable: list[str] = []
    skipped: list[str] = []
    for name in BENCHMARK_BASELINE_MODELS:
        if name == "exp_smoothing" and not exp_smoothing_available():
            skipped.append(name)
            continue
        runnable.append(name)
    return runnable, skipped


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Benchmark forecasting baselines (rolling-origin).")
    p.add_argument("--db-path", type=Path, default=DB_PATH)
    p.add_argument("--source", default="fact_appointment", choices=("auto", "fact_appointment", "vw_daily_kpis"))
    p.add_argument("--horizon", type=int, default=14, help="Backtest / future horizon (days).")
    p.add_argument("--step", type=int, default=7, help="Rolling-origin step (days).")
    p.add_argument("--season-length", type=int, default=7)
    p.add_argument("--initial-train-size", type=int, default=None)
    p.add_argument("--runs-dir", type=Path, default=None)
    p.add_argument(
        "--json-out",
        type=Path,
        default=REPO_ROOT / "ml" / "experiments" / "forecast_baseline_benchmark.json",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    args = parse_args(argv)

    load = load_daily_series(
        db_path=args.db_path,
        source=args.source,
        specialty_id=None,
        specialty_name=None,
    )
    series = load.series
    LOGGER.info(
        "Series %s → %s (%s pts) source=%s",
        series.index.min().date(),
        series.index.max().date(),
        len(series),
        load.source,
    )

    models, skipped = resolve_benchmark_models()
    if skipped:
        LOGGER.warning("Skipped models (missing dependency): %s", skipped)

    runs_root = Path(args.runs_dir) if args.runs_dir else default_runs_root()
    initial_train = args.initial_train_size or max(56, int(len(series) * 0.6))

    per_model: dict[str, Any] = {}
    metrics_for_selection: dict[str, dict[str, float]] = {}

    for model_name in models:
        kwargs = model_kwargs_for(model_name, args.season_length)
        config = ExperimentConfig(
            experiment_type="forecasting",
            name=f"forecast_baseline_{model_name}_all",
            question=(
                "Sobre demanda diaria de citas (mart), ¿qué baseline clásico "
                "minimiza MASE en rolling-origin?"
            ),
            hypothesis=(
                "Seasonal naive (semana) debería superar naive/MA si hay estacionalidad semanal "
                "estable; MASE es la métrica de selección."
            ),
            dataset=f"sqlite://{args.db_path}#{load.source}",
            target="appointments_total (daily count)",
            baseline="naive_last",
            seed=42,
            params={
                "pipeline": "forecast_baseline_benchmark",
                "model": model_name,
                "model_kwargs": kwargs,
                "selection_metric": PRIMARY_SELECTION_METRIC,
                "backtest": {
                    "protocol": "rolling_origin_expanding",
                    "horizon": args.horizon,
                    "step": args.step,
                    "initial_train_size": initial_train,
                    "season_length": args.season_length,
                },
                "connected_to_decisions": False,
            },
            notes="Baseline benchmark only. Not wired to prescriptive decisions.",
        )
        run = start_run(config, base_dir=runs_root)
        LOGGER.info("Started %s → %s", run.run_id, run.run_dir)

        try:
            result = train_and_evaluate_forecaster(
                series,
                model_name=model_name,
                model_kwargs=kwargs,
                forecast_horizon=args.horizon,
                backtest_enabled=True,
                initial_train_size=initial_train,
                backtest_step=args.step,
                backtest_horizon=args.horizon,
                season_length=args.season_length,
            )
            assert result.backtest is not None

            models_dir = run.models_dir()
            models_dir.mkdir(parents=True, exist_ok=True)
            joblib.dump(result.model, models_dir / f"forecast_{model_name}.joblib")

            pred_dir = run.predictions_dir()
            pred_dir.mkdir(parents=True, exist_ok=True)
            result.backtest.predictions.to_csv(pred_dir / "backtest_predictions.csv", index=False)
            result.backtest.metrics_by_horizon.to_csv(
                pred_dir / "metrics_by_horizon.csv", index=False
            )
            future = result.forecast.rename("y_pred").reset_index()
            future.columns = ["ds", "y_pred"]
            future.to_csv(pred_dir / "forecast_future.csv", index=False)

            overall = dict(result.backtest.overall_metrics)
            metrics_payload = {
                "model": model_name,
                "selection_metric": PRIMARY_SELECTION_METRIC,
                "overall": overall,
                "metrics_by_horizon": result.backtest.metrics_by_horizon.to_dict(orient="records"),
                "split": {
                    "protocol": "rolling_origin_expanding",
                    "horizon": args.horizon,
                    "step": args.step,
                    "initial_train_size": initial_train,
                    "n_folds": overall.get("n_folds"),
                },
                "series": {
                    "n": len(series),
                    "start": str(series.index.min().date()),
                    "end": str(series.index.max().date()),
                    "mean": float(series.mean()),
                    "std": float(series.std(ddof=0)),
                    "zero_rate": float((series == 0).mean()),
                },
                "connected_to_decisions": False,
            }
            save_metrics(run, _json_safe(metrics_payload), merge=False)
            run.metadata.artifacts.update(
                {
                    "backtest_predictions": "predictions/backtest_predictions.csv",
                    "metrics_by_horizon": "predictions/metrics_by_horizon.csv",
                    "forecast_future": "predictions/forecast_future.csv",
                    "model": f"models/forecast_{model_name}.joblib",
                }
            )
            finish_run(run, status="completed")
            (run.run_dir / "report.md").write_text(
                _model_report(run.run_id, model_name, overall, PRIMARY_SELECTION_METRIC),
                encoding="utf-8",
            )

            per_model[model_name] = {
                "run_id": run.run_id,
                "run_dir": str(run.run_dir),
                "overall": overall,
                "metrics_by_horizon": result.backtest.metrics_by_horizon.to_dict(orient="records"),
            }
            metrics_for_selection[model_name] = overall
            LOGGER.info(
                "%s MASE=%.4f MAE=%.4f WAPE=%.2f",
                model_name,
                overall.get("mase", float("nan")),
                overall.get("mae", float("nan")),
                overall.get("wape", float("nan")),
            )
        except Exception as exc:
            LOGGER.exception("Model %s failed: %s", model_name, exc)
            if run.metadata.status not in ("completed", "failed", "discarded"):
                finish_run(run, status="failed", error=str(exc))
            raise

    winner = select_best_model(metrics_for_selection, metric=PRIMARY_SELECTION_METRIC)
    # Error diagnosis on winner
    win_preds = pd.read_csv(
        Path(per_model[winner]["run_dir"]) / "predictions" / "backtest_predictions.csv"
    )
    error_diag = diagnose_errors(win_preds, series)

    summary = {
        "selection_metric": PRIMARY_SELECTION_METRIC,
        "selection_rule": f"minimize {PRIMARY_SELECTION_METRIC} on pooled rolling-origin predictions",
        "winner": winner,
        "winner_metrics": metrics_for_selection[winner],
        "models": per_model,
        "skipped_models": skipped,
        "series": {
            "source": load.source,
            "n": len(series),
            "start": str(series.index.min().date()),
            "end": str(series.index.max().date()),
            "mean": float(series.mean()),
            "std": float(series.std(ddof=0)),
            "zero_rate": float((series == 0).mean()),
        },
        "backtest": {
            "protocol": "rolling_origin_expanding",
            "horizon": args.horizon,
            "step": args.step,
            "initial_train_size": initial_train,
        },
        "error_diagnosis_winner": error_diag,
        "connected_to_decisions": False,
    }

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(_json_safe(summary), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(_json_safe({
        "winner": winner,
        "selection_metric": PRIMARY_SELECTION_METRIC,
        "metrics": {k: metrics_for_selection[k] for k in metrics_for_selection},
        "skipped": skipped,
        "error_diagnosis": error_diag,
        "json_out": str(args.json_out),
    }), indent=2, ensure_ascii=False))
    return 0


def diagnose_errors(preds: pd.DataFrame, series: pd.Series) -> dict[str, Any]:
    """Principal sources of error for the winning model."""
    df = preds.copy()
    df["ds"] = pd.to_datetime(df["ds"])
    df["abs_err"] = (df["y_true"] - df["y_pred"]).abs()
    df["dow"] = df["ds"].dt.dayofweek
    by_h = df.groupby("horizon")["abs_err"].mean().sort_values(ascending=False)
    by_dow = df.groupby("dow")["abs_err"].mean().sort_values(ascending=False)
    zero_mask = df["y_true"] == 0
    zero_rate = float((series == 0).mean())
    mae_zero = float(df.loc[zero_mask, "abs_err"].mean()) if zero_mask.any() else None
    mae_nz = float(df.loc[~zero_mask, "abs_err"].mean()) if (~zero_mask).any() else None
    if zero_rate >= 0.3:
        driver = "zero_inflation_sparse_daily_demand"
    elif mae_zero is not None and mae_nz is not None and mae_zero > mae_nz:
        driver = "errors_concentrated_on_zero_days"
    else:
        driver = "level_shift_or_dow_mismatch"
    return {
        "mean_abs_err": float(df["abs_err"].mean()),
        "worst_horizon": int(by_h.index[0]) if len(by_h) else None,
        "mae_by_horizon_top3": {str(int(k)): float(v) for k, v in by_h.head(3).items()},
        "worst_dow": int(by_dow.index[0]) if len(by_dow) else None,
        "mae_on_zero_days": mae_zero,
        "mae_on_nonzero_days": mae_nz,
        "series_zero_rate": zero_rate,
        "primary_error_driver": driver,
    }


def _model_report(run_id: str, model: str, overall: dict[str, float], metric: str) -> str:
    def fmt(key: str) -> str:
        v = overall.get(key)
        return f"{v:.4f}" if isinstance(v, (int, float)) else "N/A"

    return f"""# Forecast baseline — `{model}`

| Campo | Valor |
|-------|-------|
| run_id | `{run_id}` |
| selection_metric | `{metric}` |
| MAE | {fmt("mae")} |
| RMSE | {fmt("rmse")} |
| WAPE | {fmt("wape")} |
| sMAPE | {fmt("smape")} |
| MASE | {fmt("mase")} |
| folds | {fmt("n_folds")} |

No conectado a decisiones.
"""


if __name__ == "__main__":
    raise SystemExit(main())
