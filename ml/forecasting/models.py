"""Forecasting model abstractions and concrete implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

try:
    from prophet import Prophet
except Exception:  # pragma: no cover - optional dependency
    Prophet = None  # type: ignore[assignment]

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
except Exception:  # pragma: no cover - optional dependency
    ExponentialSmoothing = None  # type: ignore[assignment]


def exp_smoothing_available() -> bool:
    return ExponentialSmoothing is not None


def prophet_available() -> bool:
    return Prophet is not None


class BaseForecaster(ABC):
    """Common interface for all forecasting models in this package."""

    @abstractmethod
    def fit(self, series: pd.Series) -> "BaseForecaster":
        """Fit forecaster using a univariate time series."""

    @abstractmethod
    def predict(self, horizon: int, index: pd.DatetimeIndex | None = None) -> pd.Series:
        """Predict future values for the given horizon."""


@dataclass
class NaiveLastValueForecaster(BaseForecaster):
    """Baseline forecaster that repeats the last observed value."""

    fitted_: bool = False
    last_value_: float | None = None

    def fit(self, series: pd.Series) -> "NaiveLastValueForecaster":
        clean = _validate_series(series)
        self.last_value_ = float(clean.iloc[-1])
        self.fitted_ = True
        return self

    def predict(self, horizon: int, index: pd.DatetimeIndex | None = None) -> pd.Series:
        _ensure_fitted(self.fitted_)
        horizon = _validate_horizon(horizon)
        idx = index if index is not None else pd.RangeIndex(start=0, stop=horizon)
        return pd.Series(self.last_value_, index=idx, dtype=float)


@dataclass
class SeasonalNaiveForecaster(BaseForecaster):
    """Baseline forecaster that repeats values from a fixed seasonal lag."""

    season_length: int = 7
    fitted_: bool = False
    tail_values_: np.ndarray | None = None

    def fit(self, series: pd.Series) -> "SeasonalNaiveForecaster":
        clean = _validate_series(series)
        if len(clean) < self.season_length:
            raise ValueError(
                f"Need at least {self.season_length} samples for seasonal naive baseline."
            )
        self.tail_values_ = clean.iloc[-self.season_length :].astype(float).to_numpy()
        self.fitted_ = True
        return self

    def predict(self, horizon: int, index: pd.DatetimeIndex | None = None) -> pd.Series:
        _ensure_fitted(self.fitted_)
        horizon = _validate_horizon(horizon)
        assert self.tail_values_ is not None
        values = [self.tail_values_[i % self.season_length] for i in range(horizon)]
        idx = index if index is not None else pd.RangeIndex(start=0, stop=horizon)
        return pd.Series(values, index=idx, dtype=float)


@dataclass
class MovingAverageForecaster(BaseForecaster):
    """Simple moving average of the last ``window`` observations, repeated forward."""

    window: int = 7
    fitted_: bool = False
    mean_value_: float | None = None

    def fit(self, series: pd.Series) -> "MovingAverageForecaster":
        clean = _validate_series(series)
        w = int(self.window)
        if w <= 0:
            raise ValueError("window must be > 0")
        if len(clean) < w:
            raise ValueError(f"Need at least {w} samples for moving average.")
        self.mean_value_ = float(clean.iloc[-w:].mean())
        self.fitted_ = True
        return self

    def predict(self, horizon: int, index: pd.DatetimeIndex | None = None) -> pd.Series:
        _ensure_fitted(self.fitted_)
        horizon = _validate_horizon(horizon)
        idx = index if index is not None else pd.RangeIndex(start=0, stop=horizon)
        return pd.Series(self.mean_value_, index=idx, dtype=float)


@dataclass
class ProphetForecaster(BaseForecaster):
    """Wrapper around Prophet for daily demand forecasting."""

    yearly_seasonality: bool = True
    weekly_seasonality: bool = True
    daily_seasonality: bool = False
    changepoint_prior_scale: float = 0.05

    fitted_: bool = False
    model_: Any | None = None
    train_index_: pd.DatetimeIndex | None = None

    def fit(self, series: pd.Series) -> "ProphetForecaster":
        if Prophet is None:
            raise ImportError("Prophet is not installed. Add 'prophet' to dependencies.")

        clean = _validate_series(series)
        train_df = clean.rename("y").reset_index().rename(columns={clean.index.name or "index": "ds"})

        model = Prophet(
            yearly_seasonality=self.yearly_seasonality,
            weekly_seasonality=self.weekly_seasonality,
            daily_seasonality=self.daily_seasonality,
            changepoint_prior_scale=self.changepoint_prior_scale,
        )
        model.fit(train_df)

        self.model_ = model
        self.train_index_ = clean.index
        self.fitted_ = True
        return self

    def predict(self, horizon: int, index: pd.DatetimeIndex | None = None) -> pd.Series:
        _ensure_fitted(self.fitted_)
        horizon = _validate_horizon(horizon)
        assert self.model_ is not None
        assert self.train_index_ is not None

        pred_index = index if index is not None else _future_daily_index(self.train_index_, horizon)
        future_df = pd.DataFrame({"ds": pd.DatetimeIndex(pred_index)})
        forecast_df = self.model_.predict(future_df)
        return pd.Series(forecast_df["yhat"].astype(float).to_numpy(), index=pred_index)


@dataclass
class ExponentialSmoothingForecaster(BaseForecaster):
    """Statsmodels Holt-Winters forecaster for trend/seasonality patterns."""

    trend: str | None = "add"
    seasonal: str | None = "add"
    seasonal_periods: int = 7

    fitted_: bool = False
    model_: Any | None = None
    train_index_: pd.DatetimeIndex | None = None

    def fit(self, series: pd.Series) -> "ExponentialSmoothingForecaster":
        if ExponentialSmoothing is None:
            raise ImportError(
                "statsmodels is not installed. Add 'statsmodels' to dependencies."
            )

        clean = _validate_series(series)
        model = ExponentialSmoothing(
            clean,
            trend=self.trend,
            seasonal=self.seasonal,
            seasonal_periods=self.seasonal_periods,
        ).fit(optimized=True)

        self.model_ = model
        self.train_index_ = clean.index
        self.fitted_ = True
        return self

    def predict(self, horizon: int, index: pd.DatetimeIndex | None = None) -> pd.Series:
        _ensure_fitted(self.fitted_)
        horizon = _validate_horizon(horizon)
        assert self.model_ is not None
        assert self.train_index_ is not None

        pred_index = index if index is not None else _future_daily_index(self.train_index_, horizon)
        forecast = self.model_.forecast(horizon)
        return pd.Series(np.asarray(forecast, dtype=float), index=pred_index)


AVAILABLE_MODELS: tuple[str, ...] = (
    "naive_last",
    "seasonal_naive",
    "moving_average",
    "prophet",
    "exp_smoothing",
)

BENCHMARK_BASELINE_MODELS: tuple[str, ...] = (
    "naive_last",
    "seasonal_naive",
    "moving_average",
    "exp_smoothing",
)


def build_forecaster(model_name: str, **kwargs: Any) -> BaseForecaster:
    """Factory for forecasting models used by scripts and app layer."""
    normalized = model_name.strip().lower()
    if normalized == "naive_last":
        return NaiveLastValueForecaster(**kwargs)
    if normalized == "seasonal_naive":
        return SeasonalNaiveForecaster(**kwargs)
    if normalized == "moving_average":
        return MovingAverageForecaster(**kwargs)
    if normalized == "prophet":
        return ProphetForecaster(**kwargs)
    if normalized == "exp_smoothing":
        return ExponentialSmoothingForecaster(**kwargs)

    raise ValueError(
        f"Unsupported model '{model_name}'. Expected one of: {', '.join(AVAILABLE_MODELS)}"
    )


def _validate_series(series: pd.Series) -> pd.Series:
    if series.empty:
        raise ValueError("Input series is empty.")
    if not isinstance(series.index, pd.DatetimeIndex):
        raise TypeError("Input series must use a DatetimeIndex.")
    clean = series.sort_index().astype(float)
    if clean.isna().any():
        clean = clean.ffill().bfill()
    return clean


def _validate_horizon(horizon: int) -> int:
    if horizon <= 0:
        raise ValueError("Forecast horizon must be > 0.")
    return horizon


def _future_daily_index(index: pd.DatetimeIndex, horizon: int) -> pd.DatetimeIndex:
    last_ts = index[-1]
    return pd.date_range(start=last_ts + pd.Timedelta(days=1), periods=horizon, freq="D")


def _ensure_fitted(is_fitted: bool) -> None:
    if not is_fitted:
        raise RuntimeError("Model is not fitted. Call fit() first.")
