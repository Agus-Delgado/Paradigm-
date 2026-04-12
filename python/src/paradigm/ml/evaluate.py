"""Métricas de ranking y utilidad operativa (captura en top fracción)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


def top_fraction_capture(
    y_true: np.ndarray | pd.Series,
    y_score: np.ndarray,
    fraction: float = 0.1,
) -> dict[str, float]:
    """
    Fracción de positivos (no-shows) que caen en el top `fraction` por score descendente.
    Interpretación operativa: si priorizamos ese slice para contacto / recordatorio.
    """
    y = np.asarray(y_true).astype(int)
    s = np.asarray(y_score, dtype=float)
    n = len(y)
    if n == 0:
        return {"n": 0.0, "positives_in_top_fraction": 0.0, "capture_rate": float("nan")}
    k = max(1, int(np.ceil(n * fraction)))
    order = np.argsort(-s)
    top_idx = order[:k]
    pos_total = y.sum()
    pos_in_top = y[top_idx].sum()
    return {
        "n": float(n),
        "k_top": float(k),
        "positives_total": float(pos_total),
        "positives_in_top_fraction": float(pos_in_top),
        "capture_rate": float(pos_in_top / pos_total) if pos_total > 0 else float("nan"),
        "baseline_positive_rate": float(pos_total / n),
        "rate_in_top_fraction": float(pos_in_top / k),
    }


def classification_metrics(y_true: np.ndarray | pd.Series, y_score: np.ndarray) -> dict[str, Any]:
    y = np.asarray(y_true).astype(int)
    s = np.asarray(y_score, dtype=float)
    out: dict[str, Any] = {}
    if len(np.unique(y)) < 2:
        out["roc_auc"] = None
        out["average_precision"] = None
        out["brier"] = None
        out["note"] = "Una sola clase en el conjunto; métricas de ranking no aplican."
        return out
    out["roc_auc"] = float(roc_auc_score(y, s))
    out["average_precision"] = float(average_precision_score(y, s))
    out["brier"] = float(brier_score_loss(y, s))
    return out
