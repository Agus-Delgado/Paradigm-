"""Forecasting package API."""

from .evaluation import (
    PRIMARY_SELECTION_METRIC,
    BacktestResult,
    compute_regression_metrics,
    mae,
    mase,
    metrics_by_horizon,
    rmse,
    rolling_backtest,
    select_best_model,
    seasonal_naive_scale,
    smape,
    wape,
)
from .models import (
    AVAILABLE_MODELS,
    BENCHMARK_BASELINE_MODELS,
    BaseForecaster,
    MovingAverageForecaster,
    NaiveLastValueForecaster,
    SeasonalNaiveForecaster,
    build_forecaster,
    exp_smoothing_available,
)
from .trainer import ForecastTrainingResult, train_and_evaluate_forecaster

__all__ = [
    "AVAILABLE_MODELS",
    "BENCHMARK_BASELINE_MODELS",
    "PRIMARY_SELECTION_METRIC",
    "BacktestResult",
    "BaseForecaster",
    "ForecastTrainingResult",
    "MovingAverageForecaster",
    "NaiveLastValueForecaster",
    "SeasonalNaiveForecaster",
    "build_forecaster",
    "compute_regression_metrics",
    "exp_smoothing_available",
    "mae",
    "mase",
    "metrics_by_horizon",
    "rmse",
    "rolling_backtest",
    "select_best_model",
    "seasonal_naive_scale",
    "smape",
    "train_and_evaluate_forecaster",
    "wape",
]
