"""Training orchestration helpers for forecasting experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .evaluation import BacktestResult, rolling_backtest
from .models import BaseForecaster, build_forecaster


@dataclass
class ForecastTrainingResult:
    """Unified output for one forecasting training run."""

    model_name: str
    model: BaseForecaster
    forecast: pd.Series
    backtest: BacktestResult | None
    config: dict[str, Any]


def train_and_evaluate_forecaster(
    series: pd.Series,
    *,
    model_name: str,
    model_kwargs: dict[str, Any] | None = None,
    forecast_horizon: int = 30,
    backtest_enabled: bool = True,
    initial_train_size: int | None = None,
    backtest_step: int = 7,
    backtest_horizon: int | None = None,
    season_length: int = 7,
) -> ForecastTrainingResult:
    """Fit selected forecasting model and optionally run rolling-origin backtesting."""
    model_kwargs = model_kwargs or {}
    clean = series.sort_index().astype(float)

    model = build_forecaster(model_name, **model_kwargs)
    model.fit(clean)
    forecast = model.predict(forecast_horizon)

    backtest_result: BacktestResult | None = None
    if backtest_enabled:
        min_train = max(28, int(len(clean) * 0.7))
        effective_initial_train = initial_train_size or min_train
        effective_horizon = (
            backtest_horizon
            if backtest_horizon is not None
            else min(14, max(7, forecast_horizon // 2))
        )
        backtest_result = rolling_backtest(
            clean,
            model_factory=lambda: build_forecaster(model_name, **model_kwargs),
            initial_train_size=effective_initial_train,
            horizon=effective_horizon,
            step=backtest_step,
            season_length=season_length,
        )

    config = {
        "model_name": model_name,
        "model_kwargs": model_kwargs,
        "forecast_horizon": forecast_horizon,
        "backtest_enabled": backtest_enabled,
        "initial_train_size": initial_train_size,
        "backtest_step": backtest_step,
        "backtest_horizon": backtest_horizon,
        "season_length": season_length,
    }
    return ForecastTrainingResult(
        model_name=model_name,
        model=model,
        forecast=forecast,
        backtest=backtest_result,
        config=config,
    )
