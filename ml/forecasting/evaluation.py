"""Forecasting evaluation helpers (metrics + temporal backtesting)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .models import BaseForecaster


@dataclass
class BacktestResult:
    """Container for fold-level and aggregate backtesting outputs."""

    predictions: pd.DataFrame
    fold_metrics: pd.DataFrame
    overall_metrics: dict[str, float]


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def smape(y_true: np.ndarray, y_pred: np.ndarray, epsilon: float = 1e-8) -> float:
    denom = np.abs(y_true) + np.abs(y_pred) + epsilon
    return float(100.0 * np.mean(2.0 * np.abs(y_pred - y_true) / denom))


def compute_regression_metrics(y_true: pd.Series, y_pred: pd.Series) -> dict[str, float]:
    """Compute standard forecasting metrics on aligned series."""
    aligned_true, aligned_pred = y_true.align(y_pred, join="inner")
    true_values = aligned_true.to_numpy(dtype=float)
    pred_values = aligned_pred.to_numpy(dtype=float)

    if true_values.size == 0:
        raise ValueError("No overlapping points between y_true and y_pred.")

    return {
        "mae": mae(true_values, pred_values),
        "rmse": rmse(true_values, pred_values),
        "smape": smape(true_values, pred_values),
    }


def rolling_backtest(
    series: pd.Series,
    model_factory: callable,
    *,
    initial_train_size: int,
    horizon: int,
    step: int = 7,
) -> BacktestResult:
    """Run expanding-window backtesting for univariate forecasts.

    Args:
        series: Datetime-indexed target series.
        model_factory: Zero-arg callable returning a new BaseForecaster.
        initial_train_size: Number of points in the first training fold.
        horizon: Forecast horizon for each fold.
        step: Number of points to move forward between folds.
    """
    clean = series.sort_index().astype(float)
    _validate_backtest_setup(clean, initial_train_size, horizon, step)

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
                "y_true": test_slice.values,
                "y_pred": pred.values,
                "fold": fold_id,
            }
        )
        all_predictions.append(frame)

        fold_metric = compute_regression_metrics(test_slice, pred)
        fold_metric["fold"] = float(fold_id)
        fold_scores.append(fold_metric)

    if not all_predictions:
        raise ValueError("Backtesting produced no folds. Check initial_train_size/horizon/step.")

    predictions_df = pd.concat(all_predictions, ignore_index=True)
    fold_metrics_df = pd.DataFrame(fold_scores)
    overall = {
        key: float(fold_metrics_df[key].mean())
        for key in ("mae", "rmse", "smape")
        if key in fold_metrics_df.columns
    }

    return BacktestResult(
        predictions=predictions_df,
        fold_metrics=fold_metrics_df,
        overall_metrics=overall,
    )


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
