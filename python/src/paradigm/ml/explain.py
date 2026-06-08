"""
SHAP: cálculo, persistencia y reporte de importancia global (hold-out test).
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from paradigm.io.paths import ML_FIGURES_DIR, SHAP_BUNDLE_PATH, SHAP_SUMMARY_PNG


def _positive_class_shap(raw_shap: Any) -> np.ndarray:
    """Normaliza salida SHAP a matriz (n_samples, n_features) para clase positiva."""
    if isinstance(raw_shap, list):
        return np.asarray(raw_shap[1] if len(raw_shap) > 1 else raw_shap[0])
    arr = np.asarray(raw_shap)
    if arr.ndim == 3:
        return arr[:, :, 1]
    return arr


def _build_explainer(
    clf: RandomForestClassifier | LogisticRegression,
    X_transformed: np.ndarray,
    model_name: str,
):
    import shap

    if isinstance(clf, RandomForestClassifier):
        return shap.TreeExplainer(clf)

    try:
        masker = shap.maskers.Independent(X_transformed)
        return shap.LinearExplainer(clf, masker)
    except Exception:
        background = shap.sample(X_transformed, min(50, len(X_transformed)), random_state=42)
        return shap.KernelExplainer(clf.predict_proba, background)


def compute_shap_values(
    pipe: Pipeline,
    X_test: pd.DataFrame,
    model_name: str = "random_forest",
) -> tuple[np.ndarray, float, list[str]]:
    """Calcula SHAP en hold-out; devuelve valores, expected_value y nombres de features."""
    prep: ColumnTransformer = pipe.named_steps["prep"]
    clf = pipe.named_steps["clf"]
    X_t = prep.transform(X_test)
    feature_names = [str(n) for n in prep.get_feature_names_out()]

    explainer = _build_explainer(clf, X_t, model_name)
    raw = explainer.shap_values(X_t)
    shap_values = _positive_class_shap(raw)

    ev = explainer.expected_value
    if isinstance(ev, (list, np.ndarray)):
        expected_value = float(ev[1] if len(ev) > 1 else ev[0])
    else:
        expected_value = float(ev)

    return shap_values, expected_value, feature_names


def mean_abs_importance(
    shap_values: np.ndarray, feature_names: list[str], top_n: int = 15
) -> list[dict[str, float]]:
    means = np.abs(shap_values).mean(axis=0)
    pairs = sorted(zip(feature_names, means), key=lambda x: -x[1])
    return [{"feature": str(a), "mean_abs_shap": float(b)} for a, b in pairs[:top_n]]


def build_test_metadata(
    test_df: pd.DataFrame,
    y_test: pd.Series,
    proba: np.ndarray,
    model_name: str,
) -> pd.DataFrame:
    meta = test_df[["appointment_id", "appointment_date", "provider_id", "specialty_id"]].copy()
    meta["appointment_date"] = meta["appointment_date"].astype(str)
    meta["y_true"] = y_test.values
    meta["predicted_proba"] = proba
    meta["model_name"] = model_name
    # appointment_id es código 'APT-NNNNN' (string), no entero
    meta["display_id"] = (
        meta["appointment_id"].astype(str).str.replace("APT-", "", regex=False).str.lstrip("0")
    )
    meta["display_id"] = meta["display_id"].replace("", "0")
    return meta.reset_index(drop=True)


def save_shap_bundle(
    bundle: dict[str, Any],
    path: Path = SHAP_BUNDLE_PATH,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)
    return path


def write_shap_summary_plot(
    shap_values: np.ndarray,
    X_transformed: np.ndarray,
    feature_names: list[str],
    out_path: Path = SHAP_SUMMARY_PNG,
) -> Path | None:
    """Guarda beeswarm PNG en ml/figures/."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import shap

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(10, 6))
    shap.summary_plot(
        shap_values,
        X_transformed,
        feature_names=feature_names,
        show=False,
        max_display=15,
    )
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close("all")
    return out_path


def compute_and_persist_shap(
    pipe: Pipeline,
    X_test: pd.DataFrame,
    test_df: pd.DataFrame,
    y_test: pd.Series,
    proba: np.ndarray,
    model_name: str = "random_forest",
) -> dict[str, Any]:
    """
    Pipeline completo: SHAP → bundle joblib → PNG → importancias.
    Falla de forma suave (warning) si SHAP no está disponible.
    """
    result: dict[str, Any] = {
        "shap_available": False,
        "bundle_path": None,
        "summary_png": None,
        "shap_importance_top": [],
    }
    try:
        shap_values, expected_value, feature_names = compute_shap_values(pipe, X_test, model_name)
        prep = pipe.named_steps["prep"]
        X_t = prep.transform(X_test)

        meta = build_test_metadata(test_df, y_test, proba, model_name)
        bundle = {
            "shap_values": shap_values,
            "expected_value": expected_value,
            "feature_names": feature_names,
            "test_meta": meta,
            "X_test_raw": X_test.reset_index(drop=True),
            "model_name": model_name,
        }
        bundle_path = save_shap_bundle(bundle)
        png_path = write_shap_summary_plot(shap_values, X_t, feature_names)
        importance = mean_abs_importance(shap_values, feature_names)

        result.update(
            {
                "shap_available": True,
                "bundle_path": str(bundle_path),
                "summary_png": str(png_path) if png_path else None,
                "shap_importance_top": importance,
                "expected_value": expected_value,
            }
        )
    except Exception as exc:
        warnings.warn(f"SHAP no calculado ({exc}); modelos guardados sin explicabilidad.", stacklevel=2)
    return result
