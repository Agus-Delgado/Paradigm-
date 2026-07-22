"""Intervención sintética: recordatorio adicional (potential outcomes)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# Misma numeración que probability.py (evitar import circular contracts↔probability).
CHANNEL_WEB = 1
CHANNEL_PHONE = 2
CHANNEL_RECEPTION = 3


@dataclass(frozen=True)
class InterventionParams:
    """
    Tratamiento = recordatorio adicional (extra_reminder), distinto de reminder_sent base.

    delta_logit < 0 reduce P(no-show). Efectos heterogéneos por segmento.
    """

    enabled: bool = False
    treatment_prob: float = 0.5
    cost_per_intervention: float = 1.0
    # Efecto base en el logit (control → tratado)
    delta_base: float = -0.35
    # Heterogeneidad (se suman al base)
    delta_lead_long: float = -0.25  # lead >= 14
    delta_channel_web: float = -0.20
    delta_channel_phone: float = -0.05
    delta_channel_reception: float = 0.0
    delta_hour_late: float = -0.10  # hour >= 15
    delta_first_visit: float = -0.15
    delta_repeat: float = -0.05
    require_lead_at_least: int = 1
    # Segmentos usados para reportes de CATE
    segment_defs: tuple[str, ...] = (
        "lead_bin",
        "channel",
        "hour_bin",
        "recurrence",
    )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["segment_defs"] = list(self.segment_defs)
        return d


# Columnas observables de asignación (no son features de riesgo pre-booking)
INTERVENTION_ASSIGNMENT_COLUMNS: tuple[str, ...] = (
    "extra_reminder",
    "intervention_cost",
)

# Solo truth / potential outcomes — leakage si entran a modelos de riesgo
INTERVENTION_TRUTH_COLUMNS: tuple[str, ...] = (
    "true_logit_t0",
    "true_logit_t1",
    "true_p0",
    "true_p1",
    "true_ite_probability",
    "true_y0",
    "true_y1",
    "true_ite",
)


def treatment_logit_delta(
    *,
    lead_time_days: float,
    channel_id: int,
    appointment_hour: int,
    is_repeat_patient: int,
    params: InterventionParams,
) -> float:
    """Δ logit bajo tratamiento (extra reminder). Negativo ⇒ menos no-show."""
    d = float(params.delta_base)
    if lead_time_days >= 14:
        d += float(params.delta_lead_long)
    if channel_id == CHANNEL_WEB:
        d += float(params.delta_channel_web)
    elif channel_id == CHANNEL_PHONE:
        d += float(params.delta_channel_phone)
    elif channel_id == CHANNEL_RECEPTION:
        d += float(params.delta_channel_reception)
    if appointment_hour >= 15:
        d += float(params.delta_hour_late)
    if int(is_repeat_patient) == 0:
        d += float(params.delta_first_visit)
    else:
        d += float(params.delta_repeat)
    return d


def assign_treatment(
    *,
    rng: Any,
    lead_time_days: float,
    params: InterventionParams,
) -> int:
    """Asignación Bernoulli; 0 si lead insuficiente."""
    if not params.enabled:
        return 0
    if lead_time_days < params.require_lead_at_least:
        return 0
    return int(rng.random() < float(params.treatment_prob))


def segment_labels(
    *,
    lead_time_days: float,
    channel_id: int,
    appointment_hour: int,
    is_repeat_patient: int,
) -> dict[str, str]:
    if lead_time_days <= 3:
        lead_bin = "0-3"
    elif lead_time_days <= 7:
        lead_bin = "4-7"
    elif lead_time_days <= 14:
        lead_bin = "8-14"
    elif lead_time_days <= 30:
        lead_bin = "15-30"
    else:
        lead_bin = "31+"
    channel = {CHANNEL_WEB: "WEB", CHANNEL_PHONE: "PHONE", CHANNEL_RECEPTION: "RECEPTION"}.get(
        int(channel_id), str(channel_id)
    )
    if appointment_hour < 12:
        hour_bin = "8-11"
    elif appointment_hour < 15:
        hour_bin = "12-14"
    else:
        hour_bin = "15-17"
    recurrence = "repeat" if int(is_repeat_patient) == 1 else "first"
    return {
        "lead_bin": lead_bin,
        "channel": channel,
        "hour_bin": hour_bin,
        "recurrence": recurrence,
    }
