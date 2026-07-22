"""Métricas de uplift: Qini, deciles y policy value (sin política de costos)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def uplift_score_from_probs(p0: np.ndarray, p1: np.ndarray) -> np.ndarray:
    """Reducción esperada de no-show: μ̂(X,0) − μ̂(X,1). Mayor ⇒ priorizar tratamiento."""
    return np.asarray(p0, dtype=float) - np.asarray(p1, dtype=float)


def true_benefit_from_ite_probability(true_ite_probability: np.ndarray) -> np.ndarray:
    """Beneficio verdadero en escala de probabilidad: −ITE_p = p0 − p1."""
    return -np.asarray(true_ite_probability, dtype=float)


def _ordered_indices(scores: np.ndarray) -> np.ndarray:
    # Desempates estables por índice
    order = np.argsort(-scores, kind="mergesort")
    return order


def cumulative_gain(scores: np.ndarray, benefits: np.ndarray) -> np.ndarray:
    """Ganancia acumulada de ``benefits`` ordenando por ``scores`` descendente."""
    order = _ordered_indices(scores)
    return np.cumsum(benefits[order])


def area_under_cumulative(cum: np.ndarray) -> float:
    """Área bajo la curva de ganancia acumulada (trapecio normalizado por n)."""
    n = len(cum)
    if n == 0:
        return 0.0
    xs = np.arange(1, n + 1, dtype=float) / n
    ys = cum / max(n, 1)
    return float(np.trapezoid(ys, xs))


def qini_metrics(
    scores: np.ndarray,
    benefits: np.ndarray,
) -> dict[str, float]:
    """
    Qini / AUUC sobre beneficio verdadero (p0−p1).

    - ``auuc``: área bajo ganancia acumulada del ranking predicho
    - ``auuc_random``: ranking aleatorio ≈ media · (fracción)
    - ``auuc_perfect``: ranking por beneficio verdadero
    - ``qini_coefficient``: (AUUC − random) / (perfect − random), clip [−1, 1]
    """
    scores = np.asarray(scores, dtype=float)
    benefits = np.asarray(benefits, dtype=float)
    n = len(scores)
    if n == 0:
        return {
            "auuc": 0.0,
            "auuc_random": 0.0,
            "auuc_perfect": 0.0,
            "qini_coefficient": 0.0,
            "total_benefit": 0.0,
        }

    total = float(benefits.sum())
    cum_pred = cumulative_gain(scores, benefits)
    cum_perfect = cumulative_gain(benefits, benefits)
    # Random: ganancia lineal hasta el total
    cum_random = total * (np.arange(1, n + 1, dtype=float) / n)

    auuc = area_under_cumulative(cum_pred)
    auuc_perfect = area_under_cumulative(cum_perfect)
    auuc_random = area_under_cumulative(cum_random)
    denom = auuc_perfect - auuc_random
    if abs(denom) < 1e-12:
        qini = 0.0
    else:
        qini = float((auuc - auuc_random) / denom)
        qini = float(np.clip(qini, -1.0, 1.0))

    return {
        "auuc": auuc,
        "auuc_random": auuc_random,
        "auuc_perfect": auuc_perfect,
        "qini_coefficient": qini,
        "total_benefit": total,
        "mean_benefit": float(benefits.mean()),
    }


def uplift_by_decile(
    scores: np.ndarray,
    benefits: np.ndarray,
    *,
    n_deciles: int = 10,
) -> list[dict[str, Any]]:
    """Media de score predicho y beneficio verdadero por decil (1 = top uplift)."""
    scores = np.asarray(scores, dtype=float)
    benefits = np.asarray(benefits, dtype=float)
    n = len(scores)
    if n == 0:
        return []

    order = _ordered_indices(scores)
    ranks = np.empty(n, dtype=int)
    ranks[order] = np.arange(n)
    # Decil 1 = mejores scores
    decile = np.minimum(n_deciles, 1 + (ranks * n_deciles) // n)

    rows: list[dict[str, Any]] = []
    for d in range(1, n_deciles + 1):
        mask = decile == d
        if not mask.any():
            continue
        rows.append(
            {
                "decile": int(d),
                "n": int(mask.sum()),
                "mean_predicted_uplift": float(scores[mask].mean()),
                "mean_true_benefit": float(benefits[mask].mean()),
            }
        )
    return rows


def policy_value_curves(
    scores: np.ndarray,
    benefits: np.ndarray,
    *,
    fractions: tuple[float, ...] = (0.1, 0.2, 0.3, 0.5, 1.0),
) -> dict[str, list[dict[str, Any]]]:
    """
    Valor de política = beneficio medio verdadero si se trata el top-f.

    Baselines:
    - ``model``: top-f por score
    - ``random``: E[benefit] (misma fracción, asignación aleatoria)
    - ``treat_all``: E[benefit] (tratar a todos)
    - ``treat_none``: 0
    """
    scores = np.asarray(scores, dtype=float)
    benefits = np.asarray(benefits, dtype=float)
    n = len(scores)
    mean_b = float(benefits.mean()) if n else 0.0
    order = _ordered_indices(scores) if n else np.array([], dtype=int)

    model_rows: list[dict[str, Any]] = []
    random_rows: list[dict[str, Any]] = []
    treat_all_rows: list[dict[str, Any]] = []
    treat_none_rows: list[dict[str, Any]] = []

    for f in fractions:
        k = max(1, int(round(n * f))) if n else 0
        k = min(k, n) if n else 0
        if k == 0:
            model_mean = 0.0
            selected_sum = 0.0
        else:
            sel = order[:k]
            model_mean = float(benefits[sel].mean())
            selected_sum = float(benefits[sel].sum())

        model_rows.append(
            {
                "fraction": float(f),
                "n_treated": int(k),
                "mean_true_benefit": model_mean,
                "total_true_benefit": selected_sum,
                "lift_vs_random": model_mean - mean_b,
            }
        )
        random_rows.append(
            {
                "fraction": float(f),
                "n_treated": int(k),
                "mean_true_benefit": mean_b,
                "total_true_benefit": mean_b * k,
            }
        )
        treat_all_rows.append(
            {
                "fraction": 1.0,
                "n_treated": int(n),
                "mean_true_benefit": mean_b,
                "total_true_benefit": mean_b * n,
            }
        )
        treat_none_rows.append(
            {
                "fraction": 0.0,
                "n_treated": 0,
                "mean_true_benefit": 0.0,
                "total_true_benefit": 0.0,
            }
        )

    return {
        "model": model_rows,
        "random": random_rows,
        "treat_all": treat_all_rows,
        "treat_none": treat_none_rows,
    }


def segment_recovery(
    df: pd.DataFrame,
    scores: np.ndarray,
    *,
    top_fraction: float = 0.2,
) -> dict[str, Any]:
    """
    ¿El top-f del uplift predicho concentra segmentos de alto efecto verdadero?

    Segmentos prioritarios del generador: lead largo, WEB, hora tarde, primera visita.
    """
    scores = np.asarray(scores, dtype=float)
    n = len(df)
    k = max(1, int(round(n * top_fraction))) if n else 0
    order = _ordered_indices(scores)
    top = df.iloc[order[:k]].copy() if k else df.iloc[0:0].copy()

    def _rates(frame: pd.DataFrame) -> dict[str, float]:
        if len(frame) == 0:
            return {
                "lead_ge_15": 0.0,
                "channel_web": 0.0,
                "hour_ge_15": 0.0,
                "first_visit": 0.0,
            }
        return {
            "lead_ge_15": float((frame["lead_time_days"] >= 15).mean()),
            "channel_web": float((frame["booking_channel_id"] == 1).mean()),
            "hour_ge_15": float((frame["appointment_hour"] >= 15).mean()),
            "first_visit": float((frame["is_repeat_patient"] == 0).mean()),
        }

    base = _rates(df)
    top_rates = _rates(top)
    lift = {k: top_rates[k] - base[k] for k in base}
    return {
        "top_fraction": float(top_fraction),
        "n_top": int(k),
        "base_rates": base,
        "top_rates": top_rates,
        "rate_lift": lift,
        "recovers_priority_segments": bool(
            lift["lead_ge_15"] > 0.02
            or lift["channel_web"] > 0.02
            or (lift["hour_ge_15"] > 0.02 and lift["first_visit"] > 0.0)
        ),
    }


def spearman_corr(a: np.ndarray, b: np.ndarray) -> float:
    """Correlación de Spearman (ranking); 0 si constante."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if len(a) < 2 or np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return 0.0
    ra = pd.Series(a).rank(method="average").to_numpy()
    rb = pd.Series(b).rank(method="average").to_numpy()
    return float(np.corrcoef(ra, rb)[0, 1])
