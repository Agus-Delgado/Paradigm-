"""UI + helpers for demand forecasting section in Streamlit app."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from app.plots import forecast_backtest_chart, forecast_history_future_chart
from app.ui import render_workspace_header
from ml.experiments.tracker import ExperimentTracker
from ml.forecasting.models import AVAILABLE_MODELS
from paradigm.io.paths import DB_PATH, ML_EXPERIMENTS_DIR, REPO_ROOT


@dataclass
class ForecastRun:
    """Single forecasting run metadata for UI selection and rendering."""

    experiment_id: str
    name: str
    run_dir: Path
    started_at_utc: str
    finished_at_utc: str | None
    status: str
    model: str
    source: str
    specialty_id: int | None
    specialty_name: str | None
    horizon: int
    metrics: dict[str, Any]


def render_forecasting_tab(tables: dict[str, pd.DataFrame], db_path_str: str, db_mtime: float) -> None:
    """Render end-to-end forecasting workspace in Streamlit."""
    _ = db_mtime
    render_workspace_header(
        "Forecasting",
        "Demanda de citas · backtesting temporal · horizon planning",
    )
    st.caption(
        "Forecast diario de demanda con registro de experimentos en `ml/experiments` "
        "usando el ExperimentTracker del proyecto."
    )

    with st.expander("Nuevo entrenamiento de forecast", expanded=False):
        render_train_controls(tables)

    runs = list_recent_forecast_runs(limit=10)
    if not runs:
        st.info("No hay runs de forecasting todavía. Entrená uno desde el panel superior.")
        st.code("python scripts/train_forecast.py --model exp_smoothing --horizon 45", language="bash")
        return

    specialty_options = ["Todas"] + sorted(
        {
            run.specialty_name
            for run in runs
            if run.specialty_name
        }
    )
    specialty_filter = st.selectbox("Filtrar runs por especialidad", specialty_options, index=0)

    filtered_runs = [
        run for run in runs if specialty_filter == "Todas" or run.specialty_name == specialty_filter
    ]
    if not filtered_runs:
        st.warning("No hay runs para la especialidad seleccionada.")
        return

    selected_run = select_run(filtered_runs)
    render_run_summary(selected_run)
    render_forecast_visuals(selected_run, db_path=Path(db_path_str))


def render_train_controls(tables: dict[str, pd.DataFrame]) -> None:
    """Controls for on-demand training from Streamlit UI."""
    left, right = st.columns(2)

    with left:
        model = st.selectbox("Modelo", AVAILABLE_MODELS, index=3)
        horizon = st.slider("Horizon (días)", min_value=30, max_value=60, value=45, step=5)
        backtest_enabled = st.checkbox("Habilitar backtesting temporal", value=True)

    with right:
        specialty_df = tables.get("specialties", pd.DataFrame())
        specialty_map = {
            "Todas": None,
            **{
                row.specialty_name: int(row.specialty_id)
                for row in specialty_df.itertuples()
            },
        }
        selected_specialty = st.selectbox("Especialidad", list(specialty_map.keys()), index=0)
        season_length = st.number_input("Season length", min_value=2, max_value=30, value=7, step=1)

    trigger = st.button("Correr nuevo forecast", type="primary", key="forecast_train_btn")
    if not trigger:
        return

    specialty_id = specialty_map[selected_specialty]
    ok, logs = run_forecast_training(
        model=model,
        horizon=horizon,
        specialty_id=specialty_id,
        season_length=int(season_length),
        backtest_enabled=backtest_enabled,
    )
    if ok:
        st.success("Forecast entrenado y registrado correctamente.")
    else:
        st.error("El entrenamiento de forecast falló. Revisá logs.")

    st.text_area("Output entrenamiento", logs, height=220)
    st.rerun()


def list_recent_forecast_runs(limit: int = 10) -> list[ForecastRun]:
    """Read latest forecasting runs from ExperimentTracker storage."""
    tracker = ExperimentTracker(base_dir=ML_EXPERIMENTS_DIR)
    runs: list[ForecastRun] = []

    for run_dir in sorted(tracker.base_dir.glob("*"), reverse=True):
        metadata_path = run_dir / "metadata.json"
        if not metadata_path.is_file():
            continue
        try:
            with metadata_path.open(encoding="utf-8") as handle:
                meta = json.load(handle)
        except Exception:
            continue

        name = str(meta.get("name", ""))
        model_type = str(meta.get("model_type", ""))
        if not (name.startswith("demand_forecast_") or model_type.startswith("forecasting_")):
            continue

        hyper = meta.get("hyperparameters", {}) or {}
        metrics = meta.get("metrics", {}) or {}
        runs.append(
            ForecastRun(
                experiment_id=str(meta.get("experiment_id", run_dir.name)),
                name=name,
                run_dir=run_dir,
                started_at_utc=str(meta.get("started_at_utc", "")),
                finished_at_utc=meta.get("finished_at_utc"),
                status=str(meta.get("status", "unknown")),
                model=str(hyper.get("model", "unknown")),
                source=str(hyper.get("source", "fact_appointment")),
                specialty_id=_to_optional_int(hyper.get("specialty_id")),
                specialty_name=_to_optional_str(hyper.get("specialty_name")),
                horizon=int(hyper.get("forecast_horizon", 0) or 0),
                metrics=metrics,
            )
        )

        if len(runs) >= limit:
            break
    return runs


def select_run(runs: list[ForecastRun]) -> ForecastRun:
    """Render run selector and return chosen run."""
    index = st.selectbox(
        "Run de forecasting",
        range(len(runs)),
        format_func=lambda i: run_label(runs[i]),
        key="forecast_run_select",
    )
    return runs[index]


def run_label(run: ForecastRun) -> str:
    metric = run.metrics.get("backtest_rmse")
    rmse_txt = f"RMSE {float(metric):.2f}" if metric is not None else "RMSE n/a"
    scope = run.specialty_name or run.specialty_id or "ALL"
    return f"{run.experiment_id} · {run.model} · {scope} · {rmse_txt}"


def render_run_summary(run: ForecastRun) -> None:
    """Top-level run metadata and performance cards."""
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Modelo", run.model)
    c2.metric("Horizon", f"{run.horizon} días")
    c3.metric("Scope", str(run.specialty_name or run.specialty_id or "ALL"))
    c4.metric("Status", run.status)

    m1, m2, m3 = st.columns(3)
    m1.metric("MAE", _fmt_metric(run.metrics.get("backtest_mae")))
    m2.metric("RMSE", _fmt_metric(run.metrics.get("backtest_rmse")))
    smape = run.metrics.get("backtest_smape")
    m3.metric("sMAPE", f"{float(smape):.2f}%" if smape is not None else "n/a")

    with st.expander("Metadata del run"):
        st.write(
            {
                "experiment_id": run.experiment_id,
                "started_at_utc": run.started_at_utc,
                "finished_at_utc": run.finished_at_utc,
                "run_dir": str(run.run_dir),
                "source": run.source,
            }
        )


def render_forecast_visuals(run: ForecastRun, db_path: Path) -> None:
    """Render historical+future forecast chart and optional backtest chart."""
    historical = load_history_for_run(db_path, run)
    forecast_df = read_forecast_csv(run.run_dir)
    st.plotly_chart(
        forecast_history_future_chart(
            historical,
            forecast_df,
            title="Serie histórica + predicción futura",
        ),
        use_container_width=True,
    )

    backtest_df = read_backtest_csv(run.run_dir)
    if not backtest_df.empty:
        st.plotly_chart(forecast_backtest_chart(backtest_df), use_container_width=True)


def load_history_for_run(db_path: Path, run: ForecastRun) -> pd.Series:
    """Rebuild historical daily series matching run scope."""
    if not db_path.is_file():
        return pd.Series(dtype=float)

    sql = """
    SELECT fa.appointment_date AS ds, COUNT(*) AS y
    FROM fact_appointment fa
    JOIN dim_specialty sp ON fa.specialty_id = sp.specialty_id
    WHERE 1 = 1
    """
    params: list[Any] = []
    if run.specialty_id is not None:
        sql += " AND fa.specialty_id = ?"
        params.append(run.specialty_id)
    elif run.specialty_name:
        sql += " AND lower(sp.specialty_name) = lower(?)"
        params.append(run.specialty_name)
    sql += " GROUP BY fa.appointment_date ORDER BY fa.appointment_date"

    with sqlite3.connect(str(db_path)) as conn:
        frame = pd.read_sql_query(sql, conn, params=params)

    if frame.empty:
        return pd.Series(dtype=float)

    frame["ds"] = pd.to_datetime(frame["ds"])
    frame = frame.sort_values("ds")
    full_index = pd.date_range(frame["ds"].min(), frame["ds"].max(), freq="D")
    series = frame.set_index("ds")["y"].astype(float).reindex(full_index, fill_value=0.0)
    series.name = "appointments_total"
    return series


def read_forecast_csv(run_dir: Path) -> pd.DataFrame:
    path = run_dir / "forecast_future.csv"
    if not path.is_file():
        return pd.DataFrame(columns=["ds", "y_pred"])
    frame = pd.read_csv(path)
    frame["ds"] = pd.to_datetime(frame["ds"])
    frame["y_pred"] = frame["y_pred"].astype(float)
    return frame


def read_backtest_csv(run_dir: Path) -> pd.DataFrame:
    path = run_dir / "backtest_predictions.csv"
    if not path.is_file():
        return pd.DataFrame(columns=["ds", "y_true", "y_pred", "fold"])
    frame = pd.read_csv(path)
    frame["ds"] = pd.to_datetime(frame["ds"])
    return frame


def run_forecast_training(
    *,
    model: str,
    horizon: int,
    specialty_id: int | None,
    season_length: int,
    backtest_enabled: bool,
) -> tuple[bool, str]:
    """Execute train_forecast script as subprocess and return status + logs."""
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "train_forecast.py"),
        "--model",
        model,
        "--horizon",
        str(horizon),
        "--season-length",
        str(season_length),
        "--db-path",
        str(DB_PATH),
    ]
    if specialty_id is not None:
        cmd.extend(["--specialty-id", str(specialty_id)])
    if not backtest_enabled:
        cmd.append("--disable-backtest")

    result = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    logs = (result.stdout or "") + "\n" + (result.stderr or "")
    return result.returncode == 0, logs.strip()


def _fmt_metric(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.4f}"
    except Exception:
        return "n/a"


def _to_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _to_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    out = str(value).strip()
    return out or None


def _parse_utc(ts: str) -> datetime:
    if not ts:
        return datetime.min
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return datetime.min
