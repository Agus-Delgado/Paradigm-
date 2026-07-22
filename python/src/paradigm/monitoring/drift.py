"""Detección simple de drift en features y prevalencia."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from paradigm.ml_v2.features import PREDECISIONAL_CATEGORICAL, PREDECISIONAL_NUMERIC
from paradigm.monitoring.features import build_clustering_frame


def _psi(expected: np.ndarray, actual: np.ndarray, *, bins: int = 10) -> float:
    """Population Stability Index para una feature numérica."""
    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)
    expected = expected[np.isfinite(expected)]
    actual = actual[np.isfinite(actual)]
    if len(expected) < 10 or len(actual) < 10:
        return 0.0
    qs = np.linspace(0, 100, bins + 1)
    cuts = np.unique(np.percentile(expected, qs))
    if len(cuts) < 3:
        return 0.0
    e_counts = np.histogram(expected, bins=cuts)[0].astype(float)
    a_counts = np.histogram(actual, bins=cuts)[0].astype(float)
    e_perc = (e_counts + 1e-6) / (e_counts.sum() + 1e-6 * len(e_counts))
    a_perc = (a_counts + 1e-6) / (a_counts.sum() + 1e-6 * len(a_counts))
    return float(np.sum((a_perc - e_perc) * np.log(a_perc / e_perc)))


def _tv_distance(p: np.ndarray, q: np.ndarray) -> float:
    """Total variation distance entre dos distribuciones discretas."""
    return float(0.5 * np.abs(p - q).sum())


def categorical_drift(
    ref: pd.Series,
    cur: pd.Series,
) -> dict[str, Any]:
    levels = sorted(set(ref.dropna().astype(str)) | set(cur.dropna().astype(str)))
    if not levels:
        return {"tv_distance": 0.0, "n_levels": 0}
    ref_p = np.array([(ref.astype(str) == lv).mean() for lv in levels], dtype=float)
    cur_p = np.array([(cur.astype(str) == lv).mean() for lv in levels], dtype=float)
    return {
        "tv_distance": _tv_distance(ref_p, cur_p),
        "n_levels": len(levels),
    }


def prevalence_drift(
    ref_y: pd.Series | np.ndarray,
    cur_y: pd.Series | np.ndarray,
) -> dict[str, Any]:
    r = float(np.mean(np.asarray(ref_y, dtype=float)))
    c = float(np.mean(np.asarray(cur_y, dtype=float)))
    return {
        "ref_prevalence": r,
        "cur_prevalence": c,
        "abs_diff": abs(c - r),
        "rel_diff": float((c - r) / r) if r > 1e-9 else None,
    }


def drift_report_between_windows(
    ref_df: pd.DataFrame,
    cur_df: pd.DataFrame,
    *,
    outcome_col: str = "target_no_show",
    psi_alert: float = 0.2,
    tv_alert: float = 0.15,
    prev_alert: float = 0.03,
) -> dict[str, Any]:
    """
    Compara ventana de referencia vs actual.

    - Numéricas: PSI
    - Categóricas: TV distance
    - Prevalencia de outcome (monitoreo; no es feature de cluster)
    """
    # Validar que solo usamos predecisionales para feature drift
    _ = build_clustering_frame(ref_df)
    _ = build_clustering_frame(cur_df)

    numeric_rows: list[dict[str, Any]] = []
    for col in PREDECISIONAL_NUMERIC:
        if col not in ref_df.columns or col not in cur_df.columns:
            continue
        psi = _psi(ref_df[col].to_numpy(), cur_df[col].to_numpy())
        mean_shift = float(cur_df[col].mean() - ref_df[col].mean())
        numeric_rows.append(
            {
                "feature": col,
                "psi": psi,
                "mean_ref": float(ref_df[col].mean()),
                "mean_cur": float(cur_df[col].mean()),
                "mean_shift": mean_shift,
                "alert": bool(psi >= psi_alert),
            }
        )

    cat_rows: list[dict[str, Any]] = []
    for col in PREDECISIONAL_CATEGORICAL:
        if col not in ref_df.columns or col not in cur_df.columns:
            continue
        block = categorical_drift(ref_df[col], cur_df[col])
        cat_rows.append(
            {
                "feature": col,
                **block,
                "alert": bool(block["tv_distance"] >= tv_alert),
            }
        )

    prev = None
    if outcome_col in ref_df.columns and outcome_col in cur_df.columns:
        prev = prevalence_drift(ref_df[outcome_col], cur_df[outcome_col])
        prev["alert"] = bool(prev["abs_diff"] >= prev_alert)

    numeric_rows.sort(key=lambda r: -r["psi"])
    cat_rows.sort(key=lambda r: -r["tv_distance"])

    alerts = [r["feature"] for r in numeric_rows if r["alert"]] + [
        r["feature"] for r in cat_rows if r["alert"]
    ]
    if prev and prev.get("alert"):
        alerts.append("prevalence_no_show")

    return {
        "n_ref": int(len(ref_df)),
        "n_cur": int(len(cur_df)),
        "numeric": numeric_rows,
        "categorical": cat_rows,
        "prevalence": prev,
        "alerts": alerts,
        "thresholds": {
            "psi_alert": psi_alert,
            "tv_alert": tv_alert,
            "prev_alert": prev_alert,
        },
    }
