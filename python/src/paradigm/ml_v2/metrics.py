"""Métricas de clasificación para el pipeline no-show v2."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)

from paradigm.ml.evaluate import top_fraction_capture


def classification_metrics_v2(
    y_true: np.ndarray | pd.Series,
    y_score: np.ndarray,
    *,
    threshold: float = 0.5,
) -> dict[str, Any]:
    y = np.asarray(y_true).astype(int)
    s = np.asarray(y_score, dtype=float)
    out: dict[str, Any] = {}
    if len(np.unique(y)) < 2:
        out.update(
            {
                "roc_auc": None,
                "average_precision": None,
                "pr_auc": None,
                "brier": None,
                "log_loss": None,
                "precision": None,
                "recall": None,
                "f1": None,
                "note": "Una sola clase en el conjunto; métricas de ranking no aplican.",
            }
        )
        return out

    pred = (s >= threshold).astype(int)
    out["roc_auc"] = float(roc_auc_score(y, s))
    ap = float(average_precision_score(y, s))
    out["average_precision"] = ap
    out["pr_auc"] = ap
    out["brier"] = float(brier_score_loss(y, s))
    out["log_loss"] = float(log_loss(y, np.clip(s, 1e-7, 1.0 - 1e-7)))
    out["precision"] = float(precision_score(y, pred, zero_division=0))
    out["recall"] = float(recall_score(y, pred, zero_division=0))
    out["f1"] = float(f1_score(y, pred, zero_division=0))
    out["top_decile"] = top_fraction_capture(y, s, fraction=0.1)
    return out


def true_p_reference_auc(
    y_true: np.ndarray | pd.Series,
    true_p: np.ndarray | pd.Series,
) -> float | None:
    y = np.asarray(y_true).astype(int)
    p = np.asarray(true_p, dtype=float)
    if len(np.unique(y)) < 2:
        return None
    return float(roc_auc_score(y, p))
