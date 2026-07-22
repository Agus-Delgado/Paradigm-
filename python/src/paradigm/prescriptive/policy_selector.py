"""Selección de política operativa (reglas actuales del lab)."""

from __future__ import annotations

from typing import Any

from paradigm.prescriptive.config import PrescriptiveConfig, SUPPORTED_POLICIES


def select_operating_policy(
    config: PrescriptiveConfig,
    *,
    has_uplift: bool,
    mean_estimated_uplift: float | None = None,
) -> dict[str, Any]:
    """
    Regla operativa:

    1. Si ``forced_policy`` → usarla (validada).
    2. ``none`` si el costo supera el beneficio esperado unitario
       ``B * max(mean_uplift, assumed_ate)`` (o solo assumed_ate si no hay uplift).
    3. ``uplift`` solo si hay uplift y ``uplift_quality >= threshold``.
    4. Default: ``risk``.
    """
    if config.forced_policy is not None:
        policy = str(config.forced_policy).strip().lower()
        if policy not in SUPPORTED_POLICIES:
            raise ValueError(f"Política no soportada: {policy}")
        return {
            "policy": policy,
            "reason": f"forced_policy={policy}",
            "economic_gate_blocked": False,
            "uplift_eligible": bool(has_uplift and config.uplift_quality >= config.uplift_quality_threshold),
        }

    uplift_ref = (
        float(mean_estimated_uplift)
        if mean_estimated_uplift is not None and mean_estimated_uplift > 0
        else float(config.assumed_ate)
    )
    expected_benefit = float(config.benefit_per_avoided) * uplift_ref
    cost = float(config.intervention_cost)
    economic_blocked = cost > expected_benefit

    uplift_eligible = bool(
        has_uplift and float(config.uplift_quality) >= float(config.uplift_quality_threshold)
    )

    if economic_blocked:
        return {
            "policy": "none",
            "reason": (
                f"intervention_cost ({cost}) > expected_benefit "
                f"(B*uplift_ref={expected_benefit:.4f}); fallback none"
            ),
            "economic_gate_blocked": True,
            "uplift_eligible": uplift_eligible,
            "uplift_ref": uplift_ref,
            "expected_benefit_unit": expected_benefit,
        }

    if uplift_eligible:
        return {
            "policy": "uplift",
            "reason": (
                f"uplift_quality={config.uplift_quality:.2f} >= "
                f"{config.uplift_quality_threshold:.2f}"
            ),
            "economic_gate_blocked": False,
            "uplift_eligible": True,
            "uplift_ref": uplift_ref,
            "expected_benefit_unit": expected_benefit,
        }

    return {
        "policy": "risk",
        "reason": (
            "default risk "
            + (
                f"(uplift_quality={config.uplift_quality:.2f} < "
                f"{config.uplift_quality_threshold:.2f})"
                if has_uplift
                else "(uplift unavailable)"
            )
        ),
        "economic_gate_blocked": False,
        "uplift_eligible": False,
        "uplift_ref": uplift_ref,
        "expected_benefit_unit": expected_benefit,
    }
