"""Análisis de umbral de decisión para no-show v2 (costos + capacidad)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score


@dataclass(frozen=True)
class ThresholdCostConfig:
    """Parámetros económicos configurables (unidades arbitrarias / ARS)."""

    cost_fp: float = 1.0
    """Costo de intervenir a quien no iba a ser no-show."""

    cost_fn: float = 5.0
    """Costo de no intervenir a un no-show real."""

    benefit_per_avoided: float = 10.0
    """Beneficio esperado por no-show evitado (TP intervenido)."""

    max_interventions: int | None = 30
    """Capacidad máxima de contactos; None = sin tope."""

    max_intervention_fraction: float | None = None
    """Si se setea, capacidad = max(1, floor(fraction * n))."""

    def resolved_capacity(self, n: int) -> int | None:
        caps: list[int] = []
        if self.max_interventions is not None:
            caps.append(int(self.max_interventions))
        if self.max_intervention_fraction is not None:
            caps.append(max(1, int(np.floor(float(self.max_intervention_fraction) * n))))
        if not caps:
            return None
        return int(min(caps))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_threshold(
    y_true: np.ndarray | pd.Series,
    y_score: np.ndarray | pd.Series,
    threshold: float,
    config: ThresholdCostConfig,
) -> dict[str, Any]:
    """
    Interviene a los de mayor score con score >= threshold, hasta la capacidad.

    Net = benefit_per_avoided * TP - cost_fp * FP - cost_fn * FN
    donde FN = positivos no intervenidos.
    """
    y = np.asarray(y_true).astype(int)
    s = np.asarray(y_score, dtype=float)
    n = len(y)
    if n == 0:
        raise ValueError("y_true vacío")

    capacity = config.resolved_capacity(n)
    order = np.argsort(-s)
    eligible_mask = s >= float(threshold)
    eligible_idx = order[eligible_mask[order]]

    if capacity is None:
        intervene_idx = eligible_idx
    else:
        intervene_idx = eligible_idx[: int(capacity)]

    intervened = np.zeros(n, dtype=bool)
    intervened[intervene_idx] = True
    n_intervened = int(intervened.sum())

    tp = int((intervened & (y == 1)).sum())
    fp = int((intervened & (y == 0)).sum())
    fn = int((~intervened & (y == 1)).sum())
    tn = int((~intervened & (y == 0)).sum())

    # Métricas de clasificación sobre la política de intervención (no solo score>=t)
    y_hat = intervened.astype(int)
    precision = float(precision_score(y, y_hat, zero_division=0))
    recall = float(recall_score(y, y_hat, zero_division=0))
    f1 = float(f1_score(y, y_hat, zero_division=0))

    total_cost = float(config.cost_fp * fp + config.cost_fn * fn)
    expected_benefit = float(config.benefit_per_avoided * tp)
    net_value = float(expected_benefit - total_cost)
    n_pos = int(y.sum())
    noop_net = float(-config.cost_fn * n_pos)
    net_vs_noop = float(net_value - noop_net)

    return {
        "threshold": float(threshold),
        "capacity": capacity,
        "n": n,
        "n_intervened": n_intervened,
        "capacity_used": n_intervened,
        "capacity_binding": bool(
            capacity is not None and int((s >= threshold).sum()) > capacity
        ),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "total_cost": total_cost,
        "expected_benefit": expected_benefit,
        "net_value": net_value,
        "noop_net_value": noop_net,
        "net_vs_noop": net_vs_noop,
    }


def sweep_thresholds(
    y_true: np.ndarray | pd.Series,
    y_score: np.ndarray | pd.Series,
    config: ThresholdCostConfig,
    *,
    thresholds: Sequence[float] | None = None,
) -> list[dict[str, Any]]:
    if thresholds is None:
        thresholds = [round(x, 3) for x in np.linspace(0.05, 0.95, 19)]
    return [evaluate_threshold(y_true, y_score, t, config) for t in thresholds]


def select_best_threshold(
    rows: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Maximiza valor neto; empates → mayor F1 → menor n_intervened → mayor threshold."""
    if not rows:
        raise ValueError("No hay filas de umbral para seleccionar")
    ranked = sorted(
        rows,
        key=lambda r: (
            float(r["net_value"]),
            float(r["f1"]),
            -int(r["n_intervened"]),
            float(r["threshold"]),
        ),
        reverse=True,
    )
    return dict(ranked[0])


def analyze_model_thresholds(
    y_true: np.ndarray | pd.Series,
    y_score: np.ndarray | pd.Series,
    *,
    model_name: str,
    config: ThresholdCostConfig,
    thresholds: Sequence[float] | None = None,
) -> dict[str, Any]:
    rows = sweep_thresholds(y_true, y_score, config, thresholds=thresholds)
    best = select_best_threshold(rows)
    return {
        "model": model_name,
        "config": config.to_dict(),
        "resolved_capacity": config.resolved_capacity(len(np.asarray(y_true))),
        "curve": rows,
        "recommended": best,
    }


def cost_sensitivity(
    y_true: np.ndarray | pd.Series,
    y_score: np.ndarray | pd.Series,
    base: ThresholdCostConfig,
    *,
    cost_fn_grid: Sequence[float] = (2.0, 5.0, 10.0, 20.0),
    benefit_grid: Sequence[float] = (5.0, 10.0, 15.0, 25.0),
) -> list[dict[str, Any]]:
    """Recomienda umbral bajo grillas de cost_fn y benefit (cost_fp fijo)."""
    out: list[dict[str, Any]] = []
    for cost_fn in cost_fn_grid:
        for benefit in benefit_grid:
            cfg = ThresholdCostConfig(
                cost_fp=base.cost_fp,
                cost_fn=float(cost_fn),
                benefit_per_avoided=float(benefit),
                max_interventions=base.max_interventions,
                max_intervention_fraction=base.max_intervention_fraction,
            )
            rows = sweep_thresholds(y_true, y_score, cfg)
            best = select_best_threshold(rows)
            out.append(
                {
                    "cost_fp": cfg.cost_fp,
                    "cost_fn": cfg.cost_fn,
                    "benefit_per_avoided": cfg.benefit_per_avoided,
                    "threshold": best["threshold"],
                    "n_intervened": best["n_intervened"],
                    "net_value": best["net_value"],
                    "precision": best["precision"],
                    "recall": best["recall"],
                }
            )
    return out


def analyze_predictions_thresholds(
    predictions: pd.DataFrame,
    config: ThresholdCostConfig,
    *,
    model_cols: dict[str, str] | None = None,
) -> dict[str, Any]:
    model_cols = model_cols or {
        "baseline_logistic": "proba_baseline_logistic",
        "random_forest": "proba_random_forest",
    }
    y = predictions["y_true"]
    models = {}
    for name, col in model_cols.items():
        block = analyze_model_thresholds(y, predictions[col], model_name=name, config=config)
        block["sensitivity"] = cost_sensitivity(y, predictions[col], config)
        models[name] = block

    recs = {name: block["recommended"] for name, block in models.items()}
    best_model = max(recs.items(), key=lambda kv: kv[1]["net_value"])[0]
    return {
        "config": config.to_dict(),
        "n": int(len(predictions)),
        "positive_rate": float(y.mean()),
        "models": models,
        "best_model_by_net_value": best_model,
        "recommendations": recs,
    }
