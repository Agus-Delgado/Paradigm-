"""Motor: integra riesgo, uplift, costos, capacidad e incertidumbre."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from paradigm.ml_v2.uplift_decision_policy import (
    UpliftPolicyCostConfig,
    evaluate_selection,
    select_indices,
)
from paradigm.prescriptive.config import PrescriptiveConfig, SUPPORTED_POLICIES
from paradigm.prescriptive.policy_selector import select_operating_policy


@dataclass
class PrescriptiveResult:
    """Salida del motor: recomendaciones + metadatos de política."""

    recommendations: pd.DataFrame
    policy_used: str
    policy_selection: dict[str, Any]
    config: dict[str, Any]
    capacity: int | None
    n_intervened: int
    comparison: dict[str, Any]
    uncertainty_summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_used": self.policy_used,
            "policy_selection": self.policy_selection,
            "config": self.config,
            "capacity": self.capacity,
            "n_intervened": self.n_intervened,
            "comparison": self.comparison,
            "uncertainty_summary": self.uncertainty_summary,
            "n_recommendations": int(len(self.recommendations)),
            "recommendations_head": self.recommendations.head(5).to_dict(orient="records"),
        }


def _resolve_risk_column(df: pd.DataFrame, preferred: str) -> str:
    candidates = [
        preferred,
        "risk",
        "proba_random_forest",
        "predicted_proba",
        "uplift_selected",  # last resort — not ideal
    ]
    for c in candidates:
        if c in df.columns and c != "uplift_selected":
            return c
    # p0 from uplift two-model
    for c in df.columns:
        if c.startswith("p0_"):
            return c
    raise KeyError(
        f"No risk column found. preferred={preferred}, columns={list(df.columns)}"
    )


def _resolve_uplift_series(df: pd.DataFrame) -> tuple[np.ndarray | None, str | None]:
    if "uplift_selected" in df.columns:
        return df["uplift_selected"].astype(float).to_numpy(), "uplift_selected"
    if "uplift" in df.columns:
        return df["uplift"].astype(float).to_numpy(), "uplift"
    for c in df.columns:
        if c.startswith("uplift_") and c != "uplift_selected":
            return df[c].astype(float).to_numpy(), c
    if "p0_random_forest" in df.columns and "p1_random_forest" in df.columns:
        u = df["p0_random_forest"].astype(float) - df["p1_random_forest"].astype(float)
        return u.to_numpy(), "p0_minus_p1_random_forest"
    if "p0_logistic_regression" in df.columns and "p1_logistic_regression" in df.columns:
        u = (
            df["p0_logistic_regression"].astype(float)
            - df["p1_logistic_regression"].astype(float)
        )
        return u.to_numpy(), "p0_minus_p1_logistic_regression"
    return None, None


def normalize_decision_inputs(
    predictions: pd.DataFrame,
    config: PrescriptiveConfig,
) -> pd.DataFrame:
    """
    Normaliza a columnas canónicas: appointment_id, risk, uplift, expected_*.

    Si no hay uplift por cita, usa ``assumed_ate`` constante (incertidumbre alta).
    """
    df = predictions.copy()
    if "appointment_id" not in df.columns:
        df["appointment_id"] = [f"row_{i}" for i in range(len(df))]

    risk_col = _resolve_risk_column(df, config.risk_column)
    risk = df[risk_col].astype(float).to_numpy()
    uplift_arr, uplift_src = _resolve_uplift_series(df)
    has_real_uplift = uplift_arr is not None
    if uplift_arr is None:
        uplift_arr = np.full(len(df), float(config.assumed_ate), dtype=float)
        uplift_src = "assumed_ate"

    b = float(config.benefit_per_avoided)
    c = float(config.intervention_cost)
    expected_benefit = b * uplift_arr
    expected_net = expected_benefit - c

    # Incertidumbre: distancia al umbral 0.5 + flag de uplift
    uncertainty = np.abs(risk - 0.5)
    out = pd.DataFrame(
        {
            "appointment_id": df["appointment_id"].astype(str).to_numpy(),
            "risk": risk,
            "uplift": uplift_arr,
            "expected_benefit": expected_benefit,
            "intervention_cost": c,
            "expected_net_value": expected_net,
            "uncertainty_risk_margin": uncertainty,
            "uplift_source": uplift_src,
            "has_estimated_uplift": bool(has_real_uplift),
        }
    )
    if "appointment_date" in df.columns:
        out["appointment_date"] = pd.to_datetime(df["appointment_date"]).dt.strftime("%Y-%m-%d")
    if "y_true" in df.columns:
        out["y_true"] = df["y_true"].astype(int).to_numpy()
    if "true_benefit" in df.columns:
        out["true_benefit"] = df["true_benefit"].astype(float).to_numpy()
    # Alias for uplift_decision_policy select_indices
    out["extra_reminder"] = 0
    return out


def _to_uplift_config(config: PrescriptiveConfig) -> UpliftPolicyCostConfig:
    return UpliftPolicyCostConfig(
        benefit_per_avoided=config.benefit_per_avoided,
        intervention_cost=config.intervention_cost,
        max_interventions=config.max_interventions,
        max_intervention_fraction=config.max_intervention_fraction,
        min_net_value=config.min_net_value,
        random_seed=config.random_seed,
    )


def compare_policies_summary(
    frame: pd.DataFrame,
    config: PrescriptiveConfig,
) -> dict[str, Any]:
    """Resume n_intervened / predicted_net para cada política soportada."""
    u_cfg = _to_uplift_config(config)
    summary: dict[str, Any] = {}
    for policy in SUPPORTED_POLICIES:
        sel = select_indices(frame, policy, u_cfg)
        metrics = evaluate_selection(frame, sel, u_cfg, policy=policy)
        summary[policy] = {
            "n_intervened": metrics["n_intervened"],
            "predicted_net_value": metrics["predicted_net_value"],
            "capacity": metrics["capacity"],
            "mean_risk_selected": metrics["mean_risk_selected"],
            "mean_uplift_selected": metrics["mean_uplift_selected"],
            "mean_env_selected": metrics["mean_env_selected"],
        }
    return summary


def build_recommendations(
    frame: pd.DataFrame,
    *,
    policy: str,
    config: PrescriptiveConfig,
    policy_reason: str,
) -> pd.DataFrame:
    """Salida estructurada por cita."""
    u_cfg = _to_uplift_config(config)
    selected = set(int(i) for i in select_indices(frame, policy, u_cfg))
    n = len(frame)

    # Prioridad: orden de intervención (1 = más prioritario); 0 si no actúa
    priority = np.zeros(n, dtype=int)
    if selected:
        if policy == "risk":
            order = np.argsort(-frame["risk"].to_numpy(), kind="mergesort")
        elif policy in ("uplift", "net_value"):
            order = np.argsort(-frame["expected_net_value"].to_numpy(), kind="mergesort")
        elif policy == "random":
            order = np.array(sorted(selected))
        elif policy == "treat_all":
            order = np.arange(n)
        else:
            order = np.array([], dtype=int)
        rank = 1
        for idx in order:
            if int(idx) in selected:
                priority[int(idx)] = rank
                rank += 1

    rows: list[dict[str, Any]] = []
    for i in range(n):
        intervene = i in selected
        risk = float(frame.iloc[i]["risk"])
        uplift = float(frame.iloc[i]["uplift"])
        env = float(frame.iloc[i]["expected_net_value"])
        has_u = bool(frame.iloc[i]["has_estimated_uplift"])
        explanation = _explain(
            intervene=intervene,
            policy=policy,
            risk=risk,
            uplift=uplift,
            env=env,
            policy_reason=policy_reason,
            has_uplift=has_u,
        )
        uncertainty = {
            "risk_margin_to_0_5": float(frame.iloc[i]["uncertainty_risk_margin"]),
            "uplift_available": has_u,
            "uplift_source": str(frame.iloc[i]["uplift_source"]),
            "uplift_quality": float(config.uplift_quality),
        }
        rows.append(
            {
                "appointment_id": str(frame.iloc[i]["appointment_id"]),
                "recommended_action": "intervene" if intervene else "do_not_intervene",
                "risk_score": risk,
                "uplift": uplift,
                "expected_net_value": env,
                "priority": int(priority[i]),
                "explanation": explanation,
                "policy_used": policy,
                "uncertainty": uncertainty,
            }
        )

    out = pd.DataFrame(rows)
    # Orden: intervenidos por prioridad, luego el resto por riesgo
    out["_sort"] = np.where(out["priority"] > 0, out["priority"], 10_000 + (-out["risk_score"]))
    out = out.sort_values("_sort").drop(columns=["_sort"]).reset_index(drop=True)
    return out


def _explain(
    *,
    intervene: bool,
    policy: str,
    risk: float,
    uplift: float,
    env: float,
    policy_reason: str,
    has_uplift: bool,
) -> str:
    if policy == "none":
        return f"No intervenir: política none ({policy_reason})."
    if not intervene:
        return (
            f"Fuera de capacidad/ranking bajo política `{policy}` "
            f"(risk={risk:.2f}, uplift={uplift:.3f}, ENV={env:.2f})."
        )
    base = f"Intervenir por política `{policy}`"
    if policy == "risk":
        detail = f"alto riesgo ({risk:.2f})"
    elif policy == "uplift":
        detail = f"alto uplift ({uplift:.3f})"
    elif policy == "net_value":
        detail = f"ENV={env:.2f}"
    elif policy == "random":
        detail = "selección aleatoria bajo capacidad"
    else:
        detail = "treat_all"
    uplift_note = "" if has_uplift else "; uplift asumido (ATE ref.)"
    return f"{base}: {detail}{uplift_note}. Motivo selección: {policy_reason}."


def run_prescriptive_engine(
    predictions: pd.DataFrame,
    config: PrescriptiveConfig | None = None,
) -> PrescriptiveResult:
    """Punto de entrada: selecciona política, genera recomendaciones, compara baselines."""
    config = config or PrescriptiveConfig()
    frame = normalize_decision_inputs(predictions, config)
    has_uplift = bool(frame["has_estimated_uplift"].iloc[0]) if len(frame) else False
    mean_uplift = float(frame["uplift"].mean()) if len(frame) else None

    selection = select_operating_policy(
        config,
        has_uplift=has_uplift,
        mean_estimated_uplift=mean_uplift if has_uplift else None,
    )
    policy = selection["policy"]
    recommendations = build_recommendations(
        frame,
        policy=policy,
        config=config,
        policy_reason=str(selection["reason"]),
    )
    comparison = compare_policies_summary(frame, config)
    n_intervened = int((recommendations["recommended_action"] == "intervene").sum())
    capacity = config.resolved_capacity(len(frame))

    uncertainty_summary = {
        "fraction_with_real_uplift": float(frame["has_estimated_uplift"].mean()) if len(frame) else 0.0,
        "mean_risk_margin": float(frame["uncertainty_risk_margin"].mean()) if len(frame) else None,
        "uplift_quality": float(config.uplift_quality),
        "uplift_quality_threshold": float(config.uplift_quality_threshold),
        "uplift_source": str(frame["uplift_source"].iloc[0]) if len(frame) else None,
    }

    return PrescriptiveResult(
        recommendations=recommendations,
        policy_used=policy,
        policy_selection=selection,
        config=config.to_dict(),
        capacity=capacity,
        n_intervened=n_intervened,
        comparison=comparison,
        uncertainty_summary=uncertainty_summary,
    )
