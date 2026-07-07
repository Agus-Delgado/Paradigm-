"""Rule-based intervention recommender built on no-show risk scores and demand context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class InterventionProfile:
    """Intervention policy metadata used by recommendation and simulation layers."""

    key: str
    label: str
    category: str
    min_risk: float
    max_risk: float
    effectiveness: float
    uptake_rate: float
    cost_per_action_ars: float
    default_revenue_per_slot_ars: float


DEFAULT_INTERVENTIONS: tuple[InterventionProfile, ...] = (
    InterventionProfile(
        key="early_reminder",
        label="Early reminder (48h + SMS)",
        category="reminder",
        min_risk=0.35,
        max_risk=1.00,
        effectiveness=0.20,
        uptake_rate=0.75,
        cost_per_action_ars=280.0,
        default_revenue_per_slot_ars=12_500.0,
    ),
    InterventionProfile(
        key="double_confirmation",
        label="Double confirmation (phone + WhatsApp)",
        category="outreach",
        min_risk=0.55,
        max_risk=1.00,
        effectiveness=0.30,
        uptake_rate=0.60,
        cost_per_action_ars=480.0,
        default_revenue_per_slot_ars=12_500.0,
    ),
    InterventionProfile(
        key="smart_overbooking",
        label="Controlled overbooking",
        category="overbooking",
        min_risk=0.60,
        max_risk=1.00,
        effectiveness=0.12,
        uptake_rate=0.95,
        cost_per_action_ars=100.0,
        default_revenue_per_slot_ars=12_500.0,
    ),
    InterventionProfile(
        key="priority_waitlist",
        label="Waitlist prioritization",
        category="capacity",
        min_risk=0.40,
        max_risk=1.00,
        effectiveness=0.18,
        uptake_rate=0.85,
        cost_per_action_ars=150.0,
        default_revenue_per_slot_ars=12_500.0,
    ),
)


def recommend_interventions(
    risk_scores: pd.DataFrame,
    demand_forecast: pd.DataFrame | None = None,
    interventions: Iterable[InterventionProfile] | None = None,
    *,
    top_k: int = 200,
) -> pd.DataFrame:
    """Create a prioritized intervention table from risk scores plus demand context.

    Required columns in risk_scores:
    - predicted_proba

    Optional columns leveraged when available:
    - appointment_id, patient_id, appointment_date, specialty_id
    - revenue_per_slot_ars
    - demand_pressure (if already computed upstream)

    Optional columns in demand_forecast (if demand_pressure is absent):
    - appointment_date (or ds), demand_pred, capacity
    - specialty_id (optional; used for scoped merge)
    """
    if "predicted_proba" not in risk_scores.columns:
        raise ValueError("risk_scores must include a 'predicted_proba' column.")

    frame = risk_scores.copy()
    frame["predicted_proba"] = pd.to_numeric(frame["predicted_proba"], errors="coerce").fillna(0.0)
    frame["predicted_proba"] = frame["predicted_proba"].clip(0.0, 1.0)

    frame = _merge_demand_pressure(frame, demand_forecast)
    frame["demand_pressure"] = frame["demand_pressure"].fillna(1.0).clip(0.5, 2.0)

    if "revenue_per_slot_ars" not in frame.columns:
        frame["revenue_per_slot_ars"] = np.nan

    policy_bank = tuple(interventions) if interventions is not None else DEFAULT_INTERVENTIONS
    if not policy_bank:
        raise ValueError("interventions list cannot be empty.")

    recommendations: list[dict[str, object]] = []
    sorted_frame = frame.sort_values("predicted_proba", ascending=False).head(max(top_k, 1))

    for row in sorted_frame.to_dict(orient="records"):
        risk = float(row["predicted_proba"])
        demand_pressure = float(row.get("demand_pressure", 1.0) or 1.0)
        selected, alternatives = _pick_interventions(risk, policy_bank)

        revenue_per_slot = _resolve_revenue_per_slot(
            row_value=row.get("revenue_per_slot_ars"),
            fallback=selected.default_revenue_per_slot_ars,
        )

        expected_slots = _expected_slots_recovered(
            risk=risk,
            effectiveness=selected.effectiveness,
            uptake=selected.uptake_rate,
            demand_pressure=demand_pressure,
            category=selected.category,
        )
        expected_revenue = expected_slots * revenue_per_slot
        expected_cost = selected.cost_per_action_ars * selected.uptake_rate
        net_value = expected_revenue - expected_cost

        out = dict(row)
        out.update(
            {
                "recommended_intervention": selected.key,
                "recommended_label": selected.label,
                "priority_score": _priority_score(risk, net_value, demand_pressure),
                "expected_slots_recovered": expected_slots,
                "expected_revenue_ars": expected_revenue,
                "expected_cost_ars": expected_cost,
                "expected_net_ars": net_value,
                "intervention_effectiveness": selected.effectiveness,
                "intervention_uptake": selected.uptake_rate,
                "alternative_interventions": ", ".join(p.key for p in alternatives),
            }
        )
        recommendations.append(out)

    out_df = pd.DataFrame(recommendations)
    if out_df.empty:
        return out_df

    return out_df.sort_values(
        ["priority_score", "predicted_proba"],
        ascending=[False, False],
    ).reset_index(drop=True)


def _merge_demand_pressure(
    risk_scores: pd.DataFrame,
    demand_forecast: pd.DataFrame | None,
) -> pd.DataFrame:
    if "demand_pressure" in risk_scores.columns:
        return risk_scores

    frame = risk_scores.copy()
    frame["demand_pressure"] = 1.0

    if demand_forecast is None or demand_forecast.empty:
        return frame

    forecast = demand_forecast.copy()
    if "appointment_date" not in forecast.columns and "ds" in forecast.columns:
        forecast["appointment_date"] = forecast["ds"]

    required = {"appointment_date", "demand_pred", "capacity"}
    if not required.issubset(set(forecast.columns)):
        return frame

    forecast["appointment_date"] = pd.to_datetime(forecast["appointment_date"]).dt.date
    forecast["capacity"] = pd.to_numeric(forecast["capacity"], errors="coerce").replace(0, np.nan)
    forecast["demand_pred"] = pd.to_numeric(forecast["demand_pred"], errors="coerce")
    forecast["demand_pressure"] = (forecast["demand_pred"] / forecast["capacity"]).clip(0.5, 2.0)

    if "appointment_date" not in frame.columns:
        return frame

    frame["appointment_date"] = pd.to_datetime(frame["appointment_date"]).dt.date
    merge_keys = ["appointment_date"]
    if "specialty_id" in frame.columns and "specialty_id" in forecast.columns:
        merge_keys.append("specialty_id")

    merged = frame.merge(
        forecast[merge_keys + ["demand_pressure"]],
        on=merge_keys,
        how="left",
        suffixes=("", "_forecast"),
    )
    merged["demand_pressure"] = merged["demand_pressure_forecast"].fillna(merged["demand_pressure"])
    return merged.drop(columns=["demand_pressure_forecast"], errors="ignore")


def _pick_interventions(
    risk: float,
    policies: tuple[InterventionProfile, ...],
) -> tuple[InterventionProfile, list[InterventionProfile]]:
    eligible = [p for p in policies if p.min_risk <= risk <= p.max_risk]
    if not eligible:
        selected = min(policies, key=lambda p: abs(p.min_risk - risk))
        return selected, []

    ranked = sorted(
        eligible,
        key=lambda p: (p.effectiveness * p.uptake_rate) - (p.cost_per_action_ars / 10_000.0),
        reverse=True,
    )
    return ranked[0], ranked[1:3]


def _expected_slots_recovered(
    *,
    risk: float,
    effectiveness: float,
    uptake: float,
    demand_pressure: float,
    category: str,
) -> float:
    base = risk * effectiveness * uptake
    pressure_boost = min(1.25, 0.85 + 0.25 * demand_pressure)
    overbooking_bonus = 0.05 if category == "overbooking" else 0.0
    return max(0.0, (base * pressure_boost) + overbooking_bonus)


def _resolve_revenue_per_slot(row_value: object, fallback: float) -> float:
    value = pd.to_numeric(pd.Series([row_value]), errors="coerce").iloc[0]
    if pd.isna(value) or float(value) <= 0:
        return float(fallback)
    return float(value)


def _priority_score(risk: float, net_value: float, demand_pressure: float) -> float:
    return (risk * 0.6 + min(demand_pressure, 2.0) * 0.2) * max(net_value, 0.0)
