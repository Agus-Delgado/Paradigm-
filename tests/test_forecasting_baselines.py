"""Tests del módulo de forecasting (splits, métricas, reproducibilidad)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.forecasting.evaluation import (  # noqa: E402
    PRIMARY_SELECTION_METRIC,
    compute_regression_metrics,
    mase,
    rolling_backtest,
    select_best_model,
    seasonal_naive_scale,
    wape,
)
from ml.forecasting.models import (  # noqa: E402
    MovingAverageForecaster,
    NaiveLastValueForecaster,
    SeasonalNaiveForecaster,
    build_forecaster,
    exp_smoothing_available,
)


def _synthetic_daily(n: int = 120, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    # Semanal fuerte + ruido; algunos ceros de fin de semana
    dow = idx.dayofweek.to_numpy()
    level = 5.0 + 3.0 * (dow < 5).astype(float) + rng.normal(0, 0.5, size=n)
    level = np.clip(level, 0, None)
    level[dow >= 5] = 0.0
    return pd.Series(level, index=idx, name="y")


class TestForecastMetrics(unittest.TestCase):
    def test_wape_and_mase(self) -> None:
        y = np.array([10.0, 0.0, 5.0, 5.0])
        p = np.array([8.0, 1.0, 5.0, 4.0])
        self.assertAlmostEqual(wape(y, p), 100.0 * (2 + 1 + 0 + 1) / 20.0)
        scale = 2.0
        self.assertAlmostEqual(mase(y, p, scale=scale), (2 + 1 + 0 + 1) / 4.0 / scale)

    def test_compute_includes_all_keys(self) -> None:
        y = pd.Series([1.0, 2.0, 3.0])
        p = pd.Series([1.0, 2.5, 2.0])
        m = compute_regression_metrics(y, p, mase_scale=1.0)
        for key in ("mae", "rmse", "wape", "smape", "mase"):
            self.assertIn(key, m)


class TestTemporalSplits(unittest.TestCase):
    def test_rolling_origin_no_future_leak(self) -> None:
        series = _synthetic_daily(100)
        result = rolling_backtest(
            series,
            model_factory=lambda: NaiveLastValueForecaster(),
            initial_train_size=40,
            horizon=7,
            step=7,
            season_length=7,
        )
        self.assertGreater(result.overall_metrics["n_folds"], 1)
        self.assertIn("horizon", result.predictions.columns)
        # Cada fold: predice solo el bloque test inmediato tras train
        for fold_id, g in result.predictions.groupby("fold"):
            dates = pd.to_datetime(g["ds"])
            self.assertTrue(dates.is_monotonic_increasing)
            self.assertEqual(list(g["horizon"]), list(range(1, len(g) + 1)))
        self.assertFalse(result.metrics_by_horizon.empty)
        self.assertIn(PRIMARY_SELECTION_METRIC, result.overall_metrics)

    def test_seasonal_naive_scale(self) -> None:
        y = np.array([1.0, 2, 3, 4, 5, 6, 7, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5])
        scale = seasonal_naive_scale(y, season_length=7)
        self.assertAlmostEqual(scale, 0.5)


class TestReproducibility(unittest.TestCase):
    def test_same_series_same_backtest(self) -> None:
        series = _synthetic_daily(90, seed=3)

        def run_once():
            return rolling_backtest(
                series,
                model_factory=lambda: SeasonalNaiveForecaster(season_length=7),
                initial_train_size=42,
                horizon=7,
                step=7,
            )

        a = run_once()
        b = run_once()
        self.assertEqual(a.overall_metrics["mase"], b.overall_metrics["mase"])
        self.assertEqual(a.overall_metrics["mae"], b.overall_metrics["mae"])
        pd.testing.assert_frame_equal(a.predictions, b.predictions)

    def test_moving_average_fit_predict(self) -> None:
        series = _synthetic_daily(40)
        model = MovingAverageForecaster(window=7).fit(series)
        pred = model.predict(5, index=pd.date_range(series.index[-1] + pd.Timedelta(days=1), periods=5))
        self.assertEqual(len(pred), 5)
        self.assertTrue(np.allclose(pred.to_numpy(), pred.iloc[0]))

    def test_select_best_by_mase(self) -> None:
        winner = select_best_model(
            {
                "naive_last": {"mase": 1.2, "mae": 2.0},
                "seasonal_naive": {"mase": 0.8, "mae": 2.1},
                "moving_average": {"mase": 1.0, "mae": 1.5},
            },
            metric="mase",
        )
        self.assertEqual(winner, "seasonal_naive")

    def test_build_forecaster_moving_average(self) -> None:
        model = build_forecaster("moving_average", window=5)
        self.assertIsInstance(model, MovingAverageForecaster)

    def test_exp_smoothing_availability_flag(self) -> None:
        # No debe crashear; solo reporta bool
        self.assertIsInstance(exp_smoothing_available(), bool)


if __name__ == "__main__":
    unittest.main()
