"""Entrena forecasting de demanda de citas y registra experimento reproducible.

Uso (desde raíz del repo):
  python scripts/train_forecast.py
  python scripts/train_forecast.py --model prophet --horizon 60
  python scripts/train_forecast.py --model exp_smoothing --specialty-id 3
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "python" / "src"))

from ml.experiments.tracker import ExperimentTracker  # noqa: E402
from ml.forecasting.models import AVAILABLE_MODELS  # noqa: E402
from ml.forecasting.trainer import ForecastTrainingResult, train_and_evaluate_forecaster  # noqa: E402
from paradigm.io.paths import DB_PATH, ML_EXPERIMENTS_DIR  # noqa: E402


LOGGER = logging.getLogger(__name__)


@dataclass
class SeriesLoadResult:
    """Container for loaded demand series plus context metadata."""

    series: pd.Series
    source: str
    specialty_id: int | None
    specialty_name: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train appointment demand forecasting model.")
    parser.add_argument(
        "--model",
        type=str,
        default="exp_smoothing",
        choices=AVAILABLE_MODELS,
        help="Forecasting model name.",
    )
    parser.add_argument(
        "--source",
        type=str,
        default="auto",
        choices=("auto", "vw_daily_kpis", "fact_appointment"),
        help="Data source for daily demand series.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DB_PATH,
        help="Path to SQLite mart DB.",
    )
    parser.add_argument(
        "--specialty-id",
        type=int,
        default=None,
        help="Optional specialty_id filter.",
    )
    parser.add_argument(
        "--specialty-name",
        type=str,
        default=None,
        help="Optional specialty_name filter (case-insensitive).",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=45,
        help="Forecast horizon in days.",
    )
    parser.add_argument(
        "--initial-train-size",
        type=int,
        default=None,
        help="Initial train window size for expanding-window backtest.",
    )
    parser.add_argument(
        "--backtest-step",
        type=int,
        default=7,
        help="Step size in days between backtest folds.",
    )
    parser.add_argument(
        "--disable-backtest",
        action="store_true",
        help="Disable temporal backtesting and train only once.",
    )
    parser.add_argument(
        "--season-length",
        type=int,
        default=7,
        help="Season length for seasonal_naive and exp_smoothing.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    args = parse_args()

    if args.specialty_id is not None and args.specialty_name:
        raise ValueError("Use either --specialty-id or --specialty-name, not both.")

    load_result = load_daily_series(
        db_path=args.db_path,
        source=args.source,
        specialty_id=args.specialty_id,
        specialty_name=args.specialty_name,
    )
    LOGGER.info(
        "Loaded %s points from %s (specialty=%s)",
        len(load_result.series),
        load_result.source,
        load_result.specialty_name or load_result.specialty_id or "ALL",
    )

    model_kwargs = build_model_kwargs(args)
    tracker = ExperimentTracker(base_dir=ML_EXPERIMENTS_DIR)

    experiment_name = build_experiment_name(
        model_name=args.model,
        specialty_id=load_result.specialty_id,
        specialty_name=load_result.specialty_name,
    )
    experiment_id = tracker.start_experiment(
        name=experiment_name,
        model_type=f"forecasting_{args.model}",
        hyperparameters={
            "model": args.model,
            "model_kwargs": model_kwargs,
            "forecast_horizon": args.horizon,
            "source": load_result.source,
            "specialty_id": load_result.specialty_id,
            "specialty_name": load_result.specialty_name,
            "initial_train_size": args.initial_train_size,
            "backtest_step": args.backtest_step,
            "backtest_enabled": not args.disable_backtest,
            "db_path": str(args.db_path),
        },
        notes="Demand forecasting run (Phase 2).",
    )
    LOGGER.info("Started forecasting experiment %s", experiment_id)

    train_result = train_and_evaluate_forecaster(
        load_result.series,
        model_name=args.model,
        model_kwargs=model_kwargs,
        forecast_horizon=args.horizon,
        backtest_enabled=not args.disable_backtest,
        initial_train_size=args.initial_train_size,
        backtest_step=args.backtest_step,
    )

    run_dir = tracker.run_dir
    if run_dir is None:
        raise RuntimeError("Tracker run_dir is not initialized.")

    model_filename = f"forecast_{args.model}.joblib"
    tracker.log_model(train_result.model, filename=model_filename)

    artifacts = save_run_artifacts(
        run_dir=run_dir,
        train_result=train_result,
        history=load_result.series,
    )

    metrics_payload = build_metrics_payload(train_result, load_result, args)
    tracker.log_metrics(metrics_payload)
    tracker.finish_experiment()

    print_summary(
        experiment_id=experiment_id,
        run_dir=run_dir,
        args=args,
        load_result=load_result,
        train_result=train_result,
        artifacts=artifacts,
    )


def load_daily_series(
    db_path: Path,
    source: str,
    specialty_id: int | None,
    specialty_name: str | None,
) -> SeriesLoadResult:
    if not db_path.is_file():
        raise FileNotFoundError(f"SQLite mart not found: {db_path}")

    with sqlite3.connect(str(db_path)) as conn:
        if source == "vw_daily_kpis" and (specialty_id is not None or specialty_name):
            raise ValueError("vw_daily_kpis does not support specialty filter. Use source=fact_appointment.")

        if source == "vw_daily_kpis":
            frame = pd.read_sql_query(
                """
                SELECT appointment_date AS ds, appointments_total AS y
                FROM vw_daily_kpis
                ORDER BY appointment_date
                """,
                conn,
            )
            parsed = prepare_daily_series(frame)
            return SeriesLoadResult(
                series=parsed,
                source="vw_daily_kpis",
                specialty_id=None,
                specialty_name=None,
            )

        frame = load_daily_fact_series(conn, specialty_id=specialty_id, specialty_name=specialty_name)
        parsed = prepare_daily_series(frame)

        if source == "auto" and specialty_id is None and not specialty_name:
            return SeriesLoadResult(
                series=parsed,
                source="fact_appointment",
                specialty_id=None,
                specialty_name=None,
            )

        resolved_id, resolved_name = resolve_specialty(conn, specialty_id, specialty_name)
        return SeriesLoadResult(
            series=parsed,
            source="fact_appointment",
            specialty_id=resolved_id,
            specialty_name=resolved_name,
        )


def load_daily_fact_series(
    conn: sqlite3.Connection,
    specialty_id: int | None,
    specialty_name: str | None,
) -> pd.DataFrame:
    base_sql = """
    SELECT
      fa.appointment_date AS ds,
      COUNT(*) AS y
    FROM fact_appointment fa
    JOIN dim_specialty sp ON fa.specialty_id = sp.specialty_id
    WHERE 1 = 1
    """
    params: list[Any] = []

    if specialty_id is not None:
        base_sql += " AND fa.specialty_id = ?"
        params.append(specialty_id)
    if specialty_name:
        base_sql += " AND lower(sp.specialty_name) = lower(?)"
        params.append(specialty_name.strip())

    base_sql += " GROUP BY fa.appointment_date ORDER BY fa.appointment_date"
    return pd.read_sql_query(base_sql, conn, params=params)


def resolve_specialty(
    conn: sqlite3.Connection,
    specialty_id: int | None,
    specialty_name: str | None,
) -> tuple[int | None, str | None]:
    if specialty_id is None and not specialty_name:
        return None, None

    if specialty_id is not None:
        row = conn.execute(
            "SELECT specialty_id, specialty_name FROM dim_specialty WHERE specialty_id = ?",
            (specialty_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Unknown specialty_id={specialty_id}")
        return int(row[0]), str(row[1])

    row = conn.execute(
        "SELECT specialty_id, specialty_name FROM dim_specialty WHERE lower(specialty_name) = lower(?)",
        (specialty_name.strip(),),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown specialty_name='{specialty_name}'")
    return int(row[0]), str(row[1])


def prepare_daily_series(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        raise ValueError("No rows found for selected source/specialty.")

    out = frame.copy()
    out["ds"] = pd.to_datetime(out["ds"])
    out["y"] = out["y"].astype(float)
    out = out.sort_values("ds")

    full_index = pd.date_range(out["ds"].min(), out["ds"].max(), freq="D")
    series = out.set_index("ds")["y"].reindex(full_index, fill_value=0.0)
    series.name = "appointments_total"
    series.index.name = "ds"
    return series


def build_model_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    if args.model == "seasonal_naive":
        return {"season_length": args.season_length}
    if args.model == "exp_smoothing":
        return {"trend": "add", "seasonal": "add", "seasonal_periods": args.season_length}
    if args.model == "prophet":
        return {
            "yearly_seasonality": True,
            "weekly_seasonality": True,
            "daily_seasonality": False,
            "changepoint_prior_scale": 0.05,
        }
    return {}


def build_experiment_name(
    model_name: str,
    specialty_id: int | None,
    specialty_name: str | None,
) -> str:
    scope = "all"
    if specialty_id is not None:
        scope = f"specialty_{specialty_id}"
    elif specialty_name:
        scope = specialty_name.strip().lower().replace(" ", "_")
    return f"demand_forecast_{model_name}_{scope}"


def save_run_artifacts(
    run_dir: Path,
    train_result: ForecastTrainingResult,
    history: pd.Series,
) -> dict[str, str]:
    run_dir.mkdir(parents=True, exist_ok=True)

    forecast_df = train_result.forecast.rename("y_pred").reset_index()
    forecast_df.columns = ["ds", "y_pred"]
    forecast_csv = run_dir / "forecast_future.csv"
    forecast_df.to_csv(forecast_csv, index=False)

    backtest_csv = ""
    if train_result.backtest is not None:
        backtest_csv_path = run_dir / "backtest_predictions.csv"
        train_result.backtest.predictions.to_csv(backtest_csv_path, index=False)
        backtest_csv = str(backtest_csv_path)

    metrics_json = run_dir / "forecast_metrics.json"
    with metrics_json.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "model_name": train_result.model_name,
                "backtest_overall_metrics": (
                    train_result.backtest.overall_metrics if train_result.backtest else {}
                ),
            },
            handle,
            indent=2,
            ensure_ascii=False,
        )

    backtest_plot = plot_backtest(train_result, run_dir)
    forecast_plot = plot_forecast(history, train_result.forecast, run_dir)

    return {
        "forecast_csv": str(forecast_csv),
        "backtest_csv": backtest_csv,
        "metrics_json": str(metrics_json),
        "backtest_plot": str(backtest_plot) if backtest_plot else "",
        "forecast_plot": str(forecast_plot),
    }


def plot_backtest(train_result: ForecastTrainingResult, run_dir: Path) -> Path | None:
    if train_result.backtest is None or train_result.backtest.predictions.empty:
        return None

    plot_path = run_dir / "backtest_actual_vs_predicted.png"
    pred_df = train_result.backtest.predictions.copy()
    pred_df["ds"] = pd.to_datetime(pred_df["ds"])
    pred_df = pred_df.sort_values("ds")

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(pred_df["ds"], pred_df["y_true"], label="Actual", linewidth=2)
    ax.plot(pred_df["ds"], pred_df["y_pred"], label="Predicted", linewidth=2, alpha=0.85)
    ax.set_title("Backtest temporal - Actual vs Predicted")
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Demanda diaria")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    return plot_path


def plot_forecast(history: pd.Series, forecast: pd.Series, run_dir: Path) -> Path:
    plot_path = run_dir / "forecast_history_plus_future.png"

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(history.index, history.values, label="Historical", linewidth=2)
    ax.plot(forecast.index, forecast.values, label="Forecast", linewidth=2, linestyle="--")
    ax.axvline(history.index.max(), color="black", linestyle=":", alpha=0.7)
    ax.set_title("Demanda diaria - Histórico + Forecast")
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Citas")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    return plot_path


def build_metrics_payload(
    train_result: ForecastTrainingResult,
    load_result: SeriesLoadResult,
    args: argparse.Namespace,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "forecast_horizon_days": float(args.horizon),
        "n_observations": float(len(load_result.series)),
        "history_start": str(load_result.series.index.min().date()),
        "history_end": str(load_result.series.index.max().date()),
        "series_mean": float(load_result.series.mean()),
        "series_std": float(load_result.series.std(ddof=0)),
        "specialty_id": float(load_result.specialty_id) if load_result.specialty_id is not None else None,
        "specialty_name": load_result.specialty_name,
    }

    if train_result.backtest is not None:
        payload.update({
            "backtest_folds": float(len(train_result.backtest.fold_metrics)),
            "backtest_mae": float(train_result.backtest.overall_metrics.get("mae", 0.0)),
            "backtest_rmse": float(train_result.backtest.overall_metrics.get("rmse", 0.0)),
            "backtest_smape": float(train_result.backtest.overall_metrics.get("smape", 0.0)),
        })
    return payload


def print_summary(
    experiment_id: str,
    run_dir: Path,
    args: argparse.Namespace,
    load_result: SeriesLoadResult,
    train_result: ForecastTrainingResult,
    artifacts: dict[str, str],
) -> None:
    print("\n=== Forecast Training Summary ===")
    print(f"Experiment ID: {experiment_id}")
    print(f"Run directory: {run_dir}")
    print(f"Model: {args.model}")
    print(f"Source: {load_result.source}")
    print(f"Specialty: {load_result.specialty_name or load_result.specialty_id or 'ALL'}")
    print(
        "History: "
        f"{load_result.series.index.min().date()} -> {load_result.series.index.max().date()} "
        f"({len(load_result.series)} points)"
    )
    print(f"Forecast horizon: {args.horizon} days")

    if train_result.backtest is not None:
        metrics = train_result.backtest.overall_metrics
        print("\nBacktest metrics (expanding window):")
        print(f"  MAE:   {metrics.get('mae', float('nan')):.4f}")
        print(f"  RMSE:  {metrics.get('rmse', float('nan')):.4f}")
        print(f"  sMAPE: {metrics.get('smape', float('nan')):.2f}%")
    else:
        print("\nBacktest metrics: disabled")

    print("\nArtifacts:")
    for key, value in artifacts.items():
        if value:
            print(f"  - {key}: {value}")

    print("\nNext step:")
    print("  Use this run folder in Streamlit Forecasting tab to visualize latest model outputs.")


if __name__ == "__main__":
    main()
