"""Política de decisión uplift × costos (capacidad configurable).

No modifica modelos ni hiperparámetros: opera sobre predicciones Two-Model.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Sequence

import numpy as np
import pandas as pd


POLICY_NAMES: tuple[str, ...] = (
    "none",
    "treat_all",
    "random",
    "risk",
    "uplift",
    "net_value",
)

# Políticas operativas bajo capacidad (treat_all se reporta sin tope como referencia).
CAPACITY_BOUND_POLICIES: tuple[str, ...] = (
    "none",
    "random",
    "risk",
    "uplift",
    "net_value",
)


@dataclass(frozen=True)
class UpliftPolicyCostConfig:
    """Parámetros económicos para priorizar por valor esperado."""

    benefit_per_avoided: float = 10.0
    """Beneficio por unidad de reducción de P(no-show)."""

    intervention_cost: float = 0.4
    """
    Costo fijo por intervención (recordatorio adicional).

    Default 0.4 con B=10 ⇒ break-even en uplift≈0.04 (cerca del ATE_p≈0.055),
    para que tratar-a-todos no domine ni quede siempre dominado por no intervenir.
    """

    max_interventions: int | None = 30
    """Tope absoluto de contactos en el hold-out; None = sin tope absoluto."""

    max_intervention_fraction: float | None = 0.2
    """Tope relativo; capacidad = min(topes definidos)."""

    min_net_value: float = 0.0
    """Para política net_value: solo candidatos con ENV >= este umbral."""

    random_seed: int = 42

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


def _model_columns(model_name: str) -> tuple[str, str, str]:
    return (
        f"p0_{model_name}",
        f"p1_{model_name}",
        f"uplift_{model_name}",
    )


def resolve_model_name(predictions: pd.DataFrame, model_name: str | None = None) -> str:
    if model_name:
        return model_name
    if "selected_model" in predictions.columns and len(predictions):
        return str(predictions["selected_model"].iloc[0])
    if "uplift_selected" in predictions.columns and "uplift_random_forest" in predictions.columns:
        return "random_forest"
    return "logistic_regression"


def build_decision_frame(
    predictions: pd.DataFrame,
    config: UpliftPolicyCostConfig,
    *,
    model_name: str | None = None,
) -> pd.DataFrame:
    """
    Por cita: riesgo, uplift, beneficio esperado, costo, valor neto esperado.

    risk = p̂0, uplift = p̂0−p̂1, benefit = B·uplift, net = benefit − C.
    """
    name = resolve_model_name(predictions, model_name)
    p0_col, p1_col, up_col = _model_columns(name)
    missing = [c for c in (p0_col, p1_col, up_col) if c not in predictions.columns]
    if missing:
        raise KeyError(f"Faltan columnas de predicción uplift: {missing}")

    df = predictions.copy()
    risk = df[p0_col].astype(float).to_numpy()
    uplift = df[up_col].astype(float).to_numpy()
    # Preferir uplift de columnas p0/p1 por consistencia
    uplift = df[p0_col].astype(float).to_numpy() - df[p1_col].astype(float).to_numpy()

    b = float(config.benefit_per_avoided)
    c = float(config.intervention_cost)
    expected_benefit = b * uplift
    expected_net = expected_benefit - c

    out = pd.DataFrame(
        {
            "appointment_id": df["appointment_id"].to_numpy(),
            "model_name": name,
            "risk": risk,
            "uplift": uplift,
            "expected_benefit": expected_benefit,
            "intervention_cost": c,
            "expected_net_value": expected_net,
        }
    )
    if "y_true" in df.columns:
        out["y_true"] = df["y_true"].astype(int).to_numpy()
    if "true_benefit" in df.columns:
        out["true_benefit"] = df["true_benefit"].astype(float).to_numpy()
    elif "true_ite_probability" in df.columns:
        out["true_benefit"] = (-df["true_ite_probability"].astype(float)).to_numpy()
    return out


def _capacity_k(n: int, config: UpliftPolicyCostConfig) -> int:
    cap = config.resolved_capacity(n)
    if cap is None:
        return n
    return int(min(n, max(0, cap)))


def select_indices(
    frame: pd.DataFrame,
    policy: str,
    config: UpliftPolicyCostConfig,
) -> np.ndarray:
    """Índices a intervenir según la política (capacidad aplica salvo none/treat_all)."""
    if policy not in POLICY_NAMES:
        raise ValueError(f"Política desconocida: {policy}")

    n = len(frame)
    if n == 0:
        return np.array([], dtype=int)

    idx = np.arange(n)
    if policy == "none":
        return np.array([], dtype=int)

    if policy == "treat_all":
        return idx

    k = _capacity_k(n, config)
    if k <= 0:
        return np.array([], dtype=int)

    rng = np.random.default_rng(config.random_seed)

    if policy == "random":
        return rng.choice(idx, size=k, replace=False)

    if policy == "risk":
        order = np.argsort(-frame["risk"].to_numpy(), kind="mergesort")
        return order[:k]

    if policy == "uplift":
        order = np.argsort(-frame["uplift"].to_numpy(), kind="mergesort")
        return order[:k]

    # net_value: filtrar ENV >= min, ordenar por ENV desc
    env = frame["expected_net_value"].to_numpy()
    eligible = idx[env >= float(config.min_net_value)]
    if len(eligible) == 0:
        return np.array([], dtype=int)
    order_local = np.argsort(-env[eligible], kind="mergesort")
    chosen = eligible[order_local][:k]
    return chosen


def evaluate_selection(
    frame: pd.DataFrame,
    selected: np.ndarray,
    config: UpliftPolicyCostConfig,
    *,
    policy: str,
) -> dict[str, Any]:
    """Evalúa un conjunto de intervenciones (predicho + truth si hay)."""
    n = len(frame)
    selected = np.asarray(selected, dtype=int)
    mask = np.zeros(n, dtype=bool)
    if len(selected):
        mask[selected] = True
    n_int = int(mask.sum())
    capacity = config.resolved_capacity(n)

    pred_benefit = float(frame.loc[mask, "expected_benefit"].sum()) if n_int else 0.0
    pred_cost = float(config.intervention_cost) * n_int
    pred_net = pred_benefit - pred_cost

    true_benefit_sum = None
    true_net = None
    mean_true_benefit = None
    if "true_benefit" in frame.columns:
        tb = frame["true_benefit"].to_numpy(dtype=float)
        true_benefit_sum = float(config.benefit_per_avoided * tb[mask].sum()) if n_int else 0.0
        true_net = float(true_benefit_sum - pred_cost)
        mean_true_benefit = float(tb[mask].mean()) if n_int else 0.0

    return {
        "policy": policy,
        "n": n,
        "n_intervened": n_int,
        "capacity": capacity,
        "capacity_used": n_int,
        "capacity_binding": bool(
            capacity is not None and policy not in ("none", "treat_all") and n_int >= capacity
        ),
        "mean_risk_selected": float(frame.loc[mask, "risk"].mean()) if n_int else None,
        "mean_uplift_selected": float(frame.loc[mask, "uplift"].mean()) if n_int else None,
        "mean_env_selected": float(frame.loc[mask, "expected_net_value"].mean()) if n_int else None,
        "predicted_benefit": pred_benefit,
        "intervention_cost_total": pred_cost,
        "predicted_net_value": pred_net,
        "true_benefit_scaled": true_benefit_sum,
        "true_net_value": true_net,
        "mean_true_benefit": mean_true_benefit,
    }


def compare_policies(
    predictions: pd.DataFrame,
    config: UpliftPolicyCostConfig,
    *,
    model_name: str | None = None,
    policies: Sequence[str] = POLICY_NAMES,
) -> dict[str, Any]:
    """
    Compara políticas.

    ``treat_all`` se evalúa **sin** tope de capacidad (referencia de rentabilidad media).
    El ganador operativo se elige entre políticas con capacidad
    (``CAPACITY_BOUND_POLICIES``).
    """
    frame = build_decision_frame(predictions, config, model_name=model_name)
    rows: list[dict[str, Any]] = []
    for policy in policies:
        sel = select_indices(frame, policy, config)
        rows.append(evaluate_selection(frame, sel, config, policy=policy))

    def _score(r: dict[str, Any]) -> float:
        if r.get("true_net_value") is not None:
            return float(r["true_net_value"])
        return float(r["predicted_net_value"])

    by_name = {r["policy"]: r for r in rows}
    constrained = [r for r in rows if r["policy"] in CAPACITY_BOUND_POLICIES]
    if not constrained:
        constrained = list(rows)
    ranked = sorted(constrained, key=_score, reverse=True)
    winner = ranked[0]

    vs_treat_all = None
    vs_risk = None
    if by_name.get("treat_all") is not None:
        vs_treat_all = _score(winner) - _score(by_name["treat_all"])
    if winner["policy"] != "risk" and by_name.get("risk") is not None:
        vs_risk = _score(winner) - _score(by_name["risk"])

    return {
        "config": config.to_dict(),
        "model_name": str(frame["model_name"].iloc[0]) if len(frame) else model_name,
        "n": int(len(frame)),
        "resolved_capacity": config.resolved_capacity(len(frame)),
        "policies": by_name,
        "ranking_capacity_bound": [r["policy"] for r in ranked],
        "ranking_all": [r["policy"] for r in sorted(rows, key=_score, reverse=True)],
        "winner": winner["policy"],
        "winner_metrics": winner,
        "treat_all_unconstrained_net": (
            by_name["treat_all"].get("true_net_value")
            if "treat_all" in by_name
            else None
        ),
        "improvement_vs_treat_all": vs_treat_all,
        "improvement_vs_risk": vs_risk,
        "decision_frame_summary": {
            "mean_risk": float(frame["risk"].mean()),
            "mean_uplift": float(frame["uplift"].mean()),
            "mean_expected_net_value": float(frame["expected_net_value"].mean()),
            "frac_positive_env": float((frame["expected_net_value"] > 0).mean()),
            "break_even_uplift": float(config.intervention_cost / config.benefit_per_avoided)
            if config.benefit_per_avoided
            else None,
        },
    }


def cost_sensitivity_uplift(
    predictions: pd.DataFrame,
    base: UpliftPolicyCostConfig,
    *,
    model_name: str | None = None,
    benefit_grid: Sequence[float] = (5.0, 10.0, 15.0, 25.0),
    cost_grid: Sequence[float] = (0.2, 0.4, 1.0, 2.0),
) -> list[dict[str, Any]]:
    """Ganador y nets bajo grilla de B y C (capacidad fija)."""
    out: list[dict[str, Any]] = []
    for benefit in benefit_grid:
        for cost in cost_grid:
            cfg = replace(
                base,
                benefit_per_avoided=float(benefit),
                intervention_cost=float(cost),
            )
            block = compare_policies(predictions, cfg, model_name=model_name)
            w = block["winner_metrics"]
            out.append(
                {
                    "benefit_per_avoided": float(benefit),
                    "intervention_cost": float(cost),
                    "winner": block["winner"],
                    "true_net_value": w.get("true_net_value"),
                    "predicted_net_value": w.get("predicted_net_value"),
                    "n_intervened": w.get("n_intervened"),
                    "improvement_vs_treat_all": block.get("improvement_vs_treat_all"),
                    "improvement_vs_risk": block.get("improvement_vs_risk"),
                }
            )
    return out


def analyze_uplift_decision_policy(
    predictions: pd.DataFrame,
    config: UpliftPolicyCostConfig,
    *,
    model_name: str | None = None,
    include_sensitivity: bool = True,
) -> dict[str, Any]:
    """Análisis completo: comparación + sensibilidad opcional."""
    comparison = compare_policies(predictions, config, model_name=model_name)
    result: dict[str, Any] = {
        **comparison,
        "sensitivity": (
            cost_sensitivity_uplift(predictions, config, model_name=model_name)
            if include_sensitivity
            else []
        ),
    }
    return result
