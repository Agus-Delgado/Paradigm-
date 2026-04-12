"""
Entrenamiento: split temporal, baseline logístico, Random Forest interpretable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from paradigm.ml.dataset import load_eligible_appointments
from paradigm.ml.evaluate import classification_metrics, top_fraction_capture
from paradigm.ml.features import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    add_booking_calendar_features,
    add_historical_features,
    build_model_frame,
)


def _temporal_split_by_appointment_date(
    df: pd.DataFrame, test_ratio: float
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Train = fechas estrictamente anteriores al corte; test = resto."""
    dates = np.sort(df["appointment_date"].unique())
    if len(dates) < 3:
        raise ValueError("Se necesitan al menos 3 fechas distintas para un split temporal útil.")
    cut_idx = max(1, int(len(dates) * (1.0 - test_ratio)) - 1)
    cut_idx = min(cut_idx, len(dates) - 2)
    cutoff = pd.Timestamp(dates[cut_idx])
    train = df[df["appointment_date"] <= cutoff].copy()
    test = df[df["appointment_date"] > cutoff].copy()
    if len(train) == 0 or len(test) == 0:
        raise ValueError("Split temporal vacío; ajustá test_ratio o revisá fechas.")
    return train, test, cutoff.strftime("%Y-%m-%d")


def _make_preprocess() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def _build_logistic() -> Pipeline:
    return Pipeline(
        [
            ("prep", _make_preprocess()),
            (
                "clf",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    solver="lbfgs",
                    random_state=42,
                ),
            ),
        ]
    )


def _build_rf() -> Pipeline:
    return Pipeline(
        [
            ("prep", _make_preprocess()),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=120,
                    max_depth=10,
                    min_samples_leaf=5,
                    class_weight="balanced",
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def _fit_report(
    name: str,
    pipe: Pipeline,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> dict[str, Any]:
    pipe.fit(X_train, y_train)
    proba = pipe.predict_proba(X_test)[:, 1]
    pred = pipe.predict(X_test)
    metrics = classification_metrics(y_test, proba)
    metrics["accuracy"] = float(accuracy_score(y_test, pred))
    metrics["top_decile"] = top_fraction_capture(y_test, proba, fraction=0.1)
    metrics["model_name"] = name
    return metrics


def _rf_importances(pipe: Pipeline) -> list[dict[str, float]]:
    prep: ColumnTransformer = pipe.named_steps["prep"]
    clf: RandomForestClassifier = pipe.named_steps["clf"]
    names = prep.get_feature_names_out()
    imp = clf.feature_importances_
    pairs = sorted(zip(names, imp), key=lambda x: -x[1])
    return [{"feature": str(a), "importance": float(b)} for a, b in pairs[:25]]


def run_training(
    db_path: Path,
    out_dir: Path,
    test_ratio: float = 0.2,
    random_state: int = 42,
) -> dict[str, Any]:
    """
    Pipeline completo: carga, features, split temporal, dos modelos, artefactos.
    `random_state` fija la semilla de modelos sklearn (split es puramente temporal).
    """
    _ = random_state
    out_dir.mkdir(parents=True, exist_ok=True)

    raw = load_eligible_appointments(db_path)
    df = add_booking_calendar_features(raw)
    df = add_historical_features(df)

    train_df, test_df, cutoff_str = _temporal_split_by_appointment_date(df, test_ratio=test_ratio)

    X_train, y_train = build_model_frame(train_df)
    X_test, y_test = build_model_frame(test_df)

    summary: dict[str, Any] = {
        "temporal_cutoff_appointment_date": cutoff_str,
        "test_ratio_target": test_ratio,
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
        "n_positive_train": int(y_train.sum()),
        "n_positive_test": int(y_test.sum()),
        "train_date_min": str(train_df["appointment_date"].min().date()),
        "train_date_max": str(train_df["appointment_date"].max().date()),
        "test_date_min": str(test_df["appointment_date"].min().date()),
        "test_date_max": str(test_df["appointment_date"].max().date()),
    }

    lr = _build_logistic()
    rf = _build_rf()

    metrics_lr = _fit_report("logistic_regression_baseline", lr, X_train, y_train, X_test, y_test)
    metrics_rf = _fit_report("random_forest", rf, X_train, y_train, X_test, y_test)
    metrics_rf["feature_importances_top"] = _rf_importances(rf)

    summary["metrics"] = {"baseline_logistic": metrics_lr, "random_forest": metrics_rf}

    joblib.dump(lr, out_dir / "no_show_logistic.joblib")
    joblib.dump(rf, out_dir / "no_show_random_forest.joblib")

    metrics_path = out_dir / "metrics.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(_json_safe(summary), f, indent=2, ensure_ascii=False)

    return summary


def _json_safe(obj: Any) -> Any:
    import math

    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj) if not (math.isnan(float(obj)) or math.isinf(float(obj))) else None
    return obj
