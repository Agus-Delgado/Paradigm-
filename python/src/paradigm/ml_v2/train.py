"""Entrenamiento no-show v2 sobre synthetic_v2 (paralelo a paradigm.ml.train)."""

from __future__ import annotations

import json
import math
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

from paradigm.ml_v2.dataset import load_eligible_v2
from paradigm.ml_v2.features import (
    PREDECISIONAL_CATEGORICAL,
    PREDECISIONAL_NUMERIC,
    assert_no_leakage,
    build_model_frame,
)
from paradigm.ml_v2.metrics import classification_metrics_v2, true_p_reference_auc

SELECTED_MODEL = "random_forest"


def temporal_split_by_appointment_date(
    df: pd.DataFrame, test_ratio: float
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Train = fechas <= cutoff; test = fechas estrictamente posteriores."""
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
            ("num", StandardScaler(), PREDECISIONAL_NUMERIC),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                PREDECISIONAL_CATEGORICAL,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def _build_logistic(seed: int) -> Pipeline:
    return Pipeline(
        [
            ("prep", _make_preprocess()),
            (
                "clf",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    solver="lbfgs",
                    random_state=seed,
                ),
            ),
        ]
    )


def _build_rf(seed: int) -> Pipeline:
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
                    random_state=seed,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def _predict_deterministically(
    pipe: Pipeline,
    X: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    classifier = pipe.named_steps["clf"]
    configured_n_jobs = getattr(classifier, "n_jobs", None)
    if configured_n_jobs is None:
        return pipe.predict_proba(X)[:, 1], pipe.predict(X)
    classifier.n_jobs = 1
    try:
        return pipe.predict_proba(X)[:, 1], pipe.predict(X)
    finally:
        classifier.n_jobs = configured_n_jobs


def _fit_report(
    name: str,
    pipe: Pipeline,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> dict[str, Any]:
    pipe.fit(X_train, y_train)
    proba, pred = _predict_deterministically(pipe, X_test)
    metrics = classification_metrics_v2(y_test, proba)
    metrics["accuracy"] = float(accuracy_score(y_test, pred))
    metrics["model_name"] = name
    return metrics, proba


def _rf_importances(pipe: Pipeline) -> list[dict[str, float]]:
    prep: ColumnTransformer = pipe.named_steps["prep"]
    clf: RandomForestClassifier = pipe.named_steps["clf"]
    names = prep.get_feature_names_out()
    imp = clf.feature_importances_
    pairs = sorted(zip(names, imp), key=lambda x: -x[1])
    return [{"feature": str(a), "importance": float(b)} for a, b in pairs[:25]]


def _json_safe(obj: Any) -> Any:
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


def run_training_v2(
    *,
    dataset_id: str,
    out_dir: Path,
    data_root: Path | None = None,
    test_ratio: float = 0.2,
    seed: int = 42,
) -> dict[str, Any]:
    """
    Pipeline v2: carga CSV synthetic_v2, features predecisionales, split temporal,
    LR + RF (hiperparámetros alineados a v1), artefactos bajo ``out_dir``.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw = load_eligible_v2(dataset_id, data_root=data_root)
    train_df, test_df, cutoff_str = temporal_split_by_appointment_date(raw, test_ratio=test_ratio)

    X_train, y_train = build_model_frame(train_df)
    X_test, y_test = build_model_frame(test_df)
    assert_no_leakage(X_train.columns)
    assert_no_leakage(X_test.columns)

    # Invariante temporal: train hasta cutoff inclusive; test estrictamente después.
    assert train_df["appointment_date"].max() <= pd.Timestamp(cutoff_str)
    assert test_df["appointment_date"].min() > pd.Timestamp(cutoff_str)

    summary: dict[str, Any] = {
        "dataset_id": dataset_id,
        "pipeline": "no_show_v2",
        "temporal_cutoff_appointment_date": cutoff_str,
        "test_ratio_target": test_ratio,
        "seed": seed,
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
        "n_positive_train": int(y_train.sum()),
        "n_positive_test": int(y_test.sum()),
        "train_date_min": str(train_df["appointment_date"].min().date()),
        "train_date_max": str(train_df["appointment_date"].max().date()),
        "test_date_min": str(test_df["appointment_date"].min().date()),
        "test_date_max": str(test_df["appointment_date"].max().date()),
        "features_categorical": list(PREDECISIONAL_CATEGORICAL),
        "features_numeric": list(PREDECISIONAL_NUMERIC),
        "excluded_from_features": [
            "true_logit",
            "true_no_show_probability",
            "patient_propensity_u",
            "provider_effect_v",
            "appointment_status_id",
            "status_code",
            "cancellation_ts",
            "cancellation_reason_id",
            "billing_*",
        ],
    }

    lr = _build_logistic(seed)
    rf = _build_rf(seed)

    metrics_lr, lr_proba = _fit_report(
        "logistic_regression_baseline", lr, X_train, y_train, X_test, y_test
    )
    metrics_rf, rf_proba = _fit_report("random_forest", rf, X_train, y_train, X_test, y_test)
    metrics_rf["feature_importances_top"] = _rf_importances(rf)

    true_p_auc = None
    if "true_no_show_probability" in test_df.columns:
        true_p_auc = true_p_reference_auc(y_test, test_df["true_no_show_probability"])

    summary["metrics"] = {
        "baseline_logistic": metrics_lr,
        "random_forest": metrics_rf,
    }
    summary["true_p_reference"] = {
        "roc_auc": true_p_auc,
        "note": "AUC de ranking por probabilidad generadora (referencia; no es un modelo entrenado).",
    }
    summary["selected_model"] = SELECTED_MODEL

    models_dir = out_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(lr, models_dir / "no_show_logistic.joblib")
    joblib.dump(rf, models_dir / "no_show_random_forest.joblib")

    predictions = pd.DataFrame(
        {
            "appointment_id": test_df["appointment_id"].to_numpy(),
            "appointment_date": pd.to_datetime(test_df["appointment_date"]).dt.strftime("%Y-%m-%d"),
            "y_true": y_test.to_numpy().astype(int),
            "proba_baseline_logistic": lr_proba,
            "proba_random_forest": rf_proba,
        }
    )
    if "true_no_show_probability" in test_df.columns:
        predictions["true_no_show_probability"] = (
            test_df["true_no_show_probability"].astype(float).to_numpy()
        )
    pred_path = out_dir / "predictions" / "test_predictions.csv"
    pred_path.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(pred_path, index=False)
    summary["predictions_path"] = str(pred_path)

    metrics_path = out_dir / "training_summary.json"
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(_json_safe(summary), f, indent=2, ensure_ascii=False)
    summary["training_summary_path"] = str(metrics_path)
    return summary
