"""Sensibilidad de políticas risk / uplift / net_value (capacidad, costos, calidad).

No reentrena modelos ni toca el generador: opera sobre predicciones + truth.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Sequence

import numpy as np
import pandas as pd

from paradigm.ml_v2.uplift_decision_policy import (
    CAPACITY_BOUND_POLICIES,
    UpliftPolicyCostConfig,
    build_decision_frame,
    evaluate_selection,
    select_indices,
)

FOCUS_POLICIES: tuple[str, ...] = ("none", "risk", "uplift", "net_value")


def blend_uplift_with_truth(
    predicted_uplift: np.ndarray,
    true_benefit: np.ndarray,
    quality: float,
) -> np.ndarray:
    """
    Calidad del ranking uplift: q=0 usa solo predicción; q=1 usa truth (oráculo).

    ``uplift_q = (1-q)·pred + q·true_benefit``
    """
    q = float(np.clip(quality, 0.0, 1.0))
    pred = np.asarray(predicted_uplift, dtype=float)
    truth = np.asarray(true_benefit, dtype=float)
    return (1.0 - q) * pred + q * truth


def apply_uplift_quality(frame: pd.DataFrame, quality: float) -> pd.DataFrame:
    """Recalcula uplift / beneficio / ENV con calidad interpolada (riesgo intacto)."""
    out = frame.copy()
    if "true_benefit" not in out.columns:
        if quality > 0:
            raise ValueError("Se requiere true_benefit para uplift_quality > 0")
        return out
    q = float(np.clip(quality, 0.0, 1.0))
    uplift_q = blend_uplift_with_truth(
        out["uplift"].to_numpy(dtype=float),
        out["true_benefit"].to_numpy(dtype=float),
        q,
    )
    c = float(out["intervention_cost"].iloc[0]) if len(out) else 0.0
    # B implícito: expected_benefit / uplift cuando uplift != 0; mejor pasar B
    # Usamos ratio medio seguro vía columnas existentes recalculadas fuera.
    out["uplift"] = uplift_q
    out["uplift_quality"] = q
    return out


def _recompute_economics(frame: pd.DataFrame, config: UpliftPolicyCostConfig) -> pd.DataFrame:
    out = frame.copy()
    b = float(config.benefit_per_avoided)
    c = float(config.intervention_cost)
    out["intervention_cost"] = c
    out["expected_benefit"] = b * out["uplift"].astype(float)
    out["expected_net_value"] = out["expected_benefit"] - c
    return out


def build_quality_frame(
    predictions: pd.DataFrame,
    config: UpliftPolicyCostConfig,
    *,
    model_name: str | None = None,
    uplift_quality: float = 0.0,
) -> pd.DataFrame:
    base = build_decision_frame(predictions, config, model_name=model_name)
    blended = apply_uplift_quality(base, uplift_quality)
    return _recompute_economics(blended, config)


def select_oracle_indices(frame: pd.DataFrame, config: UpliftPolicyCostConfig) -> np.ndarray:
    """Mejor política posible con truth: top-K por true ENV = B·true_benefit − C."""
    if "true_benefit" not in frame.columns:
        raise ValueError("Oracle requiere true_benefit")
    n = len(frame)
    if n == 0:
        return np.array([], dtype=int)
    b = float(config.benefit_per_avoided)
    c = float(config.intervention_cost)
    true_env = b * frame["true_benefit"].to_numpy(dtype=float) - c
    idx = np.arange(n)
    eligible = idx[true_env >= float(config.min_net_value)]
    if len(eligible) == 0:
        return np.array([], dtype=int)
    cap = config.resolved_capacity(n)
    k = n if cap is None else int(min(n, max(0, cap)))
    if k <= 0:
        return np.array([], dtype=int)
    order = np.argsort(-true_env[eligible], kind="mergesort")
    return eligible[order][:k]


def regret_vs_oracle(policy_true_net: float, oracle_true_net: float) -> float:
    """Regret = net(oráculo) − net(política); ≥ 0 si el oráculo es óptimo."""
    return float(oracle_true_net - policy_true_net)


def evaluate_policies_with_quality(
    predictions: pd.DataFrame,
    config: UpliftPolicyCostConfig,
    *,
    uplift_quality: float = 0.0,
    model_name: str | None = None,
    policies: Sequence[str] = FOCUS_POLICIES,
) -> dict[str, Any]:
    """Compara políticas focus + oráculo; reporta regret."""
    frame = build_quality_frame(
        predictions, config, model_name=model_name, uplift_quality=uplift_quality
    )
    rows: dict[str, dict[str, Any]] = {}
    for policy in policies:
        sel = select_indices(frame, policy, config)
        rows[policy] = evaluate_selection(frame, sel, config, policy=policy)

    oracle_sel = select_oracle_indices(frame, config)
    oracle = evaluate_selection(frame, oracle_sel, config, policy="oracle_truth")
    oracle_net = float(oracle["true_net_value"] or 0.0)

    regrets: dict[str, float] = {}
    for name, row in rows.items():
        pn = float(row["true_net_value"] or 0.0)
        regrets[name] = regret_vs_oracle(pn, oracle_net)

    constrained = [rows[p] for p in policies if p in CAPACITY_BOUND_POLICIES and p in rows]
    winner = max(
        constrained,
        key=lambda r: float(r["true_net_value"] or 0.0),
    )
    return {
        "uplift_quality": float(uplift_quality),
        "config": config.to_dict(),
        "resolved_capacity": config.resolved_capacity(len(frame)),
        "n": int(len(frame)),
        "policies": rows,
        "oracle": oracle,
        "regrets": regrets,
        "winner": winner["policy"],
        "winner_true_net": float(winner["true_net_value"] or 0.0),
        "oracle_true_net": oracle_net,
        "winner_regret": regrets.get(winner["policy"]),
    }


def sensitivity_grid(
    predictions: pd.DataFrame,
    *,
    model_name: str | None = None,
    capacity_grid: Sequence[int] = (10, 30, 50, 100),
    benefit_grid: Sequence[float] = (5.0, 10.0, 25.0),
    cost_grid: Sequence[float] = (0.2, 0.4, 1.0, 2.0),
    quality_grid: Sequence[float] = (0.0, 0.25, 0.5, 0.75, 1.0),
    base_seed: int = 42,
) -> list[dict[str, Any]]:
    """Grilla completa: una fila por (capacidad, B, C, calidad)."""
    rows: list[dict[str, Any]] = []
    for cap in capacity_grid:
        for benefit in benefit_grid:
            for cost in cost_grid:
                for quality in quality_grid:
                    cfg = UpliftPolicyCostConfig(
                        benefit_per_avoided=float(benefit),
                        intervention_cost=float(cost),
                        max_interventions=int(cap),
                        max_intervention_fraction=None,
                        min_net_value=0.0,
                        random_seed=base_seed,
                    )
                    block = evaluate_policies_with_quality(
                        predictions,
                        cfg,
                        uplift_quality=float(quality),
                        model_name=model_name,
                    )
                    policy_nets = {
                        name: float((block["policies"][name].get("true_net_value") or 0.0))
                        for name in FOCUS_POLICIES
                    }
                    rows.append(
                        {
                            "capacity": int(cap),
                            "benefit_per_avoided": float(benefit),
                            "intervention_cost": float(cost),
                            "uplift_quality": float(quality),
                            "winner": block["winner"],
                            "winner_true_net": block["winner_true_net"],
                            "oracle_true_net": block["oracle_true_net"],
                            "regrets": block["regrets"],
                            "policy_true_nets": policy_nets,
                            "n_intervened_winner": block["policies"][block["winner"]][
                                "n_intervened"
                            ],
                            "break_even_uplift": float(cost) / float(benefit) if benefit else None,
                        }
                    )
    return rows


def aggregate_multiseed(
    per_seed_grids: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """
    Alinea celdas por (cap, B, C, q) y resume estabilidad / regret medio.
    """
    keys = ("capacity", "benefit_per_avoided", "intervention_cost", "uplift_quality")
    buckets: dict[tuple, list[dict[str, Any]]] = {}
    for seed_id, grid in per_seed_grids.items():
        for row in grid:
            key = tuple(row[k] for k in keys)
            buckets.setdefault(key, []).append({"seed": seed_id, **row})

    cells: list[dict[str, Any]] = []
    for key, items in sorted(buckets.items()):
        winners = [it["winner"] for it in items]
        # mayoría
        counts: dict[str, int] = {}
        for w in winners:
            counts[w] = counts.get(w, 0) + 1
        majority = max(counts.items(), key=lambda kv: kv[1])[0]
        agreement = counts[majority] / len(winners)
        mean_regret = {
            p: float(np.mean([it["regrets"][p] for it in items]))
            for p in FOCUS_POLICIES
        }
        mean_nets = {
            p: float(np.mean([it["policy_true_nets"][p] for it in items]))
            for p in FOCUS_POLICIES
        }
        cells.append(
            {
                "capacity": key[0],
                "benefit_per_avoided": key[1],
                "intervention_cost": key[2],
                "uplift_quality": key[3],
                "majority_winner": majority,
                "winner_counts": counts,
                "seed_agreement": agreement,
                "stable": agreement >= 1.0,
                "mean_regret": mean_regret,
                "mean_true_net": mean_nets,
                "mean_oracle_net": float(np.mean([it["oracle_true_net"] for it in items])),
                "n_seeds": len(items),
            }
        )

    # Estabilidad global
    n_cells = len(cells)
    n_stable = sum(1 for c in cells if c["stable"])
    win_freq: dict[str, int] = {}
    for c in cells:
        w = c["majority_winner"]
        win_freq[w] = win_freq.get(w, 0) + 1

    return {
        "n_cells": n_cells,
        "n_stable_cells": n_stable,
        "stability_rate": float(n_stable / n_cells) if n_cells else 0.0,
        "majority_win_frequency": win_freq,
        "cells": cells,
    }


def detect_frontiers(
    cells: list[dict[str, Any]],
    *,
    slice_fixed: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """
    Fronteras: cambios de majority_winner al variar un eje con los otros fijos.

    Escanea todas las combinaciones de las dimensiones fijas (no solo defaults).
    """
    del slice_fixed  # API compatible; se escanea el producto completo
    axes = ("capacity", "benefit_per_avoided", "intervention_cost", "uplift_quality")
    frontiers: list[dict[str, Any]] = []
    by_key = {
        (
            c["capacity"],
            c["benefit_per_avoided"],
            c["intervention_cost"],
            c["uplift_quality"],
        ): c
        for c in cells
    }
    caps = sorted({c["capacity"] for c in cells})
    bens = sorted({c["benefit_per_avoided"] for c in cells})
    costs = sorted({c["intervention_cost"] for c in cells})
    quals = sorted({c["uplift_quality"] for c in cells})

    def _add(axis: str, prev: dict[str, Any], cur: dict[str, Any], fixed: dict[str, Any]) -> None:
        if prev["majority_winner"] == cur["majority_winner"]:
            return
        frontiers.append(
            {
                "axis": axis,
                "from_value": prev[axis],
                "to_value": cur[axis],
                "from_winner": prev["majority_winner"],
                "to_winner": cur["majority_winner"],
                "fixed": fixed,
            }
        )

    for b in bens:
        for cost in costs:
            for q in quals:
                prev = None
                for cap in caps:
                    cur = by_key[(cap, b, cost, q)]
                    if prev is not None:
                        _add(
                            "capacity",
                            prev,
                            cur,
                            {
                                "benefit_per_avoided": b,
                                "intervention_cost": cost,
                                "uplift_quality": q,
                            },
                        )
                    prev = cur

    for cap in caps:
        for cost in costs:
            for q in quals:
                prev = None
                for b in bens:
                    cur = by_key[(cap, b, cost, q)]
                    if prev is not None:
                        _add(
                            "benefit_per_avoided",
                            prev,
                            cur,
                            {
                                "capacity": cap,
                                "intervention_cost": cost,
                                "uplift_quality": q,
                            },
                        )
                    prev = cur

    for cap in caps:
        for b in bens:
            for q in quals:
                prev = None
                for cost in costs:
                    cur = by_key[(cap, b, cost, q)]
                    if prev is not None:
                        _add(
                            "intervention_cost",
                            prev,
                            cur,
                            {
                                "capacity": cap,
                                "benefit_per_avoided": b,
                                "uplift_quality": q,
                            },
                        )
                    prev = cur

    for cap in caps:
        for b in bens:
            for cost in costs:
                prev = None
                for q in quals:
                    cur = by_key[(cap, b, cost, q)]
                    if prev is not None:
                        _add(
                            "uplift_quality",
                            prev,
                            cur,
                            {
                                "capacity": cap,
                                "benefit_per_avoided": b,
                                "intervention_cost": cost,
                            },
                        )
                    prev = cur

    return frontiers


def summarize_when_each_wins(cells: list[dict[str, Any]]) -> dict[str, Any]:
    """Condiciones empíricas donde cada política es majority winner."""
    by_policy: dict[str, list[dict[str, Any]]] = {}
    for c in cells:
        by_policy.setdefault(c["majority_winner"], []).append(c)

    summary: dict[str, Any] = {}
    for policy, rows in by_policy.items():
        summary[policy] = {
            "n_cells": len(rows),
            "capacity_range": [min(r["capacity"] for r in rows), max(r["capacity"] for r in rows)],
            "benefit_range": [
                min(r["benefit_per_avoided"] for r in rows),
                max(r["benefit_per_avoided"] for r in rows),
            ],
            "cost_range": [
                min(r["intervention_cost"] for r in rows),
                max(r["intervention_cost"] for r in rows),
            ],
            "quality_range": [
                min(r["uplift_quality"] for r in rows),
                max(r["uplift_quality"] for r in rows),
            ],
            "mean_regret_of_winner": float(np.mean([r["mean_regret"][policy] for r in rows])),
            "frac_stable": float(np.mean([1.0 if r["stable"] else 0.0 for r in rows])),
        }
    return summary


def run_multiseed_sensitivity(
    predictions_by_seed: dict[str, pd.DataFrame],
    *,
    capacity_grid: Sequence[int] = (10, 30, 50, 100),
    benefit_grid: Sequence[float] = (5.0, 10.0, 25.0),
    cost_grid: Sequence[float] = (0.2, 0.4, 1.0, 2.0),
    quality_grid: Sequence[float] = (0.0, 0.25, 0.5, 0.75, 1.0),
) -> dict[str, Any]:
    """Pipeline completo multiseed."""
    per_seed: dict[str, list[dict[str, Any]]] = {}
    for seed_id, preds in predictions_by_seed.items():
        per_seed[seed_id] = sensitivity_grid(
            preds,
            capacity_grid=capacity_grid,
            benefit_grid=benefit_grid,
            cost_grid=cost_grid,
            quality_grid=quality_grid,
        )
    agg = aggregate_multiseed(per_seed)
    frontiers = detect_frontiers(agg["cells"])
    when = summarize_when_each_wins(agg["cells"])
    return {
        "grids": {
            "capacity": list(capacity_grid),
            "benefit_per_avoided": list(benefit_grid),
            "intervention_cost": list(cost_grid),
            "uplift_quality": list(quality_grid),
        },
        "per_seed_n_rows": {k: len(v) for k, v in per_seed.items()},
        "aggregate": agg,
        "frontiers": frontiers,
        "when_each_wins": when,
    }
