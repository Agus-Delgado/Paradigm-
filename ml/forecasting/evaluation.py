"""Forecasting evaluation helpers (metrics + rolling-origin backtesting)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .models import BaseForecaster

# Métrica primaria de selección en el benchmark de baselines (menor es mejor).
PRIMARY_SELECTION_METRIC = "mase"


@dataclass
class BacktestResult:
    """Container for fold-level and aggregate backtesting outputs."""

    predictions: pd.DataFrame
    fold_metrics: pd.DataFrame
    overall_metrics: dict[str, float]
    metrics_by_horizon: pd.DataFrame
    selection_metric: str = PRIMARY_SELECTION_METRIC


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def smape(y_true: np.ndarray, y_pred: np.ndarray, epsilon: float = 1e-8) -> float:
    denom = np.abs(y_true) + np.abs(y_pred) + epsilon
    return float(100.0 * np.mean(2.0 * np.abs(y_pred - y_true) / denom))


def wape(y_true: np.ndarray, y_pred: np.ndarray, epsilon: float = 1e-8) -> float:
    """Weighted Absolute Percentage Error (%): 100 * sum|e| / sum|y|."""
    denom = float(np.sum(np.abs(y_true))) + epsilon
    return float(100.0 * np.sum(np.abs(y_true - y_pred)) / denom)


def seasonal_naive_scale(
    y: np.ndarray | pd.Series,
    *,
    season_length: int = 7,
) -> float:
    """In-sample seasonal-naive MAE used as MASE denominator."""
    arr = np.asarray(y, dtype=float)
    m = int(season_length)
    if m <= 0:
        raise ValueError("season_length must be > 0")
    if len(arr) <= m:
        raise ValueError("Need more than season_length points to compute MASE scale.")
    diffs = np.abs(arr[m:] - arr[:-m])
    scale = float(np.mean(diffs))
    if scale < 1e-12:
        return 1e-12
    return scale


def mase(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    scale: float,
) -> float:
    """Mean Absolute Scaled Error (Hyndman): MAE / seasonal-naive in-sample MAE."""
    return float(mae(y_true, y_pred) / float(scale))


def compute_regression_metrics(
    y_true: pd.Series | np.ndarray,
    y_pred: pd.Series | np.ndarray,
    *,
    mase_scale: float | None = None,
) -> dict[str, float]:
    """Compute standard forecasting metrics on aligned series."""
    if isinstance(y_true, pd.Series) and isinstance(y_pred, pd.Series):
        aligned_true, aligned_pred = y_true.align(y_pred, join="inner")
        true_values = aligned_true.to_numpy(dtype=float)
        pred_values = aligned_pred.to_numpy(dtype=float)
    else:
        true_values = np.asarray(y_true, dtype=float)
        pred_values = np.asarray(y_pred, dtype=float)
        if true_values.shape != pred_values.shape:
            raise ValueError("y_true and y_pred must have the same shape.")

    if true_values.size == 0:
        raise ValueError("No overlapping points between y_true and y_pred.")

    out: dict[str, float] = {
        "mae": mae(true_values, pred_values),
        "rmse": rmse(true_values, pred_values),
        "wape": wape(true_values, pred_values),
        "smape": smape(true_values, pred_values),
    }
    if mase_scale is not None:
        out["mase"] = mase(true_values, pred_values, scale=mase_scale)
    return out


def metrics_by_horizon(
    predictions: pd.DataFrame,
    *,
    mase_scale: float | None = None,
) -> pd.DataFrame:
    """Aggregate error metrics for each forecast horizon step (1..H)."""
    if predictions.empty or "horizon" not in predictions.columns:
        return pd.DataFrame(columns=["horizon", "n", "mae", "rmse", "wape", "smape", "mase"])

    rows: list[dict[str, float]] = []
    for h, group in predictions.groupby("horizon", sort=True):
        y_t = group["y_true"].to_numpy(dtype=float)
        y_p = group["y_pred"].to_numpy(dtype=float)
        metrics = compute_regression_metrics(y_t, y_p, mase_scale=mase_scale)
        rows.append(
            {
                "horizon": float(h),
                "n": float(len(group)),
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def rolling_backtest(
    series: pd.Series,
    model_factory: Callable[[], BaseForecaster],
    *,
    initial_train_size: int,
    horizon: int,
    step: int = 7,
    season_length: int = 7,
) -> BacktestResult:
    """Rolling-origin (expanding-window) backtesting for univariate forecasts.

    Args:
        series: Datetime-indexed target series.
        model_factory: Zero-arg callable returning a new BaseForecaster.
        initial_train_size: Number of points in the first training fold.
        horizon: Forecast horizon for each fold.
        step: Number of points to move forward between folds.
        season_length: Seasonality used for MASE scale (daily demand → 7).
    """
    clean = series.sort_index().astype(float)
    _validate_backtest_setup(clean, initial_train_size, horizon, step)

    # Escala MASE fija desde el tramo de entrenamiento inicial (comparable entre modelos).
    mase_scale = seasonal_naive_scale(
        clean.iloc[:initial_train_size].to_numpy(dtype=float),
        season_length=season_length,
    )

    all_predictions: list[pd.DataFrame] = []
    fold_scores: list[dict[str, float]] = []
    fold_id = 0

    for train_end in range(initial_train_size, len(clean) - horizon + 1, step):
        fold_id += 1
        train_slice = clean.iloc[:train_end]
        test_slice = clean.iloc[train_end : train_end + horizon]

        model = model_factory()
        if not isinstance(model, BaseForecaster):
            raise TypeError("model_factory must return a BaseForecaster instance.")

        model.fit(train_slice)
        pred = model.predict(horizon=len(test_slice), index=test_slice.index)

        frame = pd.DataFrame(
            {
                "ds": test_slice.index,
                "y_true": test_slice.to_numpy(dtype=float),
                "y_pred": pred.to_numpy(dtype=float),
                "fold": fold_id,
                "horizon": np.arange(1, len(test_slice) + 1, dtype=int),
            }
        )
        all_predictions.append(frame)

        fold_metric = compute_regression_metrics(
            test_slice, pred, mase_scale=mase_scale
        )
        fold_metric["fold"] = float(fold_id)
        fold_scores.append(fold_metric)

    if not all_predictions:
        raise ValueError("Backtesting produced no folds. Check initial_train_size/horizon/step.")

    predictions_df = pd.concat(all_predictions, ignore_index=True)
    fold_metrics_df = pd.DataFrame(fold_scores)

    pooled = compute_regression_metrics(
        predictions_df["y_true"],
        predictions_df["y_pred"],
        mase_scale=mase_scale,
    )
    # También reportar media de folds (legacy) junto al pooled.
    fold_means = {
        f"fold_mean_{key}": float(fold_metrics_df[key].mean())
        for key in ("mae", "rmse", "wape", "smape", "mase")
        if key in fold_metrics_df.columns
    }
    overall = {
        **pooled,
        **fold_means,
        "mase_scale": float(mase_scale),
        "n_folds": float(fold_id),
        "n_predictions": float(len(predictions_df)),
    }
    by_h = metrics_by_horizon(predictions_df, mase_scale=mase_scale)

    return BacktestResult(
        predictions=predictions_df,
        fold_metrics=fold_metrics_df,
        overall_metrics=overall,
        metrics_by_horizon=by_h,
        selection_metric=PRIMARY_SELECTION_METRIC,
    )


def select_best_model(
    results_by_model: dict[str, dict[str, float]],
    *,
    metric: str = PRIMARY_SELECTION_METRIC,
) -> str:
    """Elige el modelo con menor valor de ``metric`` (explícito: default MASE)."""
    if not results_by_model:
        raise ValueError("No model results to select from.")
    ranked = sorted(
        results_by_model.items(),
        key=lambda kv: float(kv[1].get(metric, float("inf"))),
    )
    return ranked[0][0]


def _validate_backtest_setup(
    series: pd.Series,
    initial_train_size: int,
    horizon: int,
    step: int,
) -> None:
    if not isinstance(series.index, pd.DatetimeIndex):
        raise TypeError("Backtesting series must use a DatetimeIndex.")
    if initial_train_size <= 0:
        raise ValueError("initial_train_size must be > 0.")
    if horizon <= 0:
        raise ValueError("horizon must be > 0.")
    if step <= 0:
        raise ValueError("step must be > 0.")
    if len(series) < initial_train_size + horizon:
        raise ValueError("Not enough data points for requested initial_train_size + horizon.")
