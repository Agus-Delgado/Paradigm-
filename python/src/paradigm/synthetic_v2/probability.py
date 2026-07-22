"""Cálculo de logit / probabilidad verdadera de no-show."""

from __future__ import annotations

import math

import numpy as np

from paradigm.synthetic_v2.contracts import CoefficientParams, GeneratorConfig

# Catálogos alineados al generador v1
CHANNEL_WEB = 1
CHANNEL_PHONE = 2
CHANNEL_RECEPTION = 3
COVERAGE_PARTICULAR = 6


def sigmoid(z: float | np.ndarray) -> float | np.ndarray:
    z_arr = np.asarray(z, dtype=float)
    out = np.empty_like(z_arr, dtype=float)
    pos = z_arr >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z_arr[pos]))
    exp_z = np.exp(z_arr[~pos])
    out[~pos] = exp_z / (1.0 + exp_z)
    if np.isscalar(z):
        return float(out)
    return out


def clip_probability(p: float | np.ndarray, low: float, high: float) -> float | np.ndarray:
    return np.clip(p, low, high)


def channel_effect(channel_id: int, coef: CoefficientParams) -> float:
    if channel_id == CHANNEL_WEB:
        return coef.beta_C_web
    if channel_id == CHANNEL_PHONE:
        return coef.beta_C_phone
    return coef.beta_C_reception


def dow_effect(dow: int, coef: CoefficientParams) -> float:
    # pandas/numpy: Monday=0 ... Sunday=6
    if dow == 0:
        return coef.beta_D_mon
    if dow == 4:
        return coef.beta_D_fri
    return 0.0


def specialty_effect(specialty_id: int, coef: CoefficientParams) -> float:
    idx = int(specialty_id) - 1
    betas = coef.beta_S
    if idx < 0 or idx >= len(betas):
        return 0.0
    return float(betas[idx])


def seasonality(month: int, coef: CoefficientParams) -> float:
    return float(coef.alpha_season_month * math.sin(2.0 * math.pi * month / 12.0))


def systematic_logit(
    *,
    lead_time_days: float,
    channel_id: int,
    appointment_hour: int,
    appointment_dow: int,
    appointment_month: int,
    specialty_id: int,
    coverage_id: int,
    reminder_sent: int,
    patient_prior_no_show_rate: float,
    patient_prior_appt_count: int,
    patient_u: float,
    provider_v: float,
    coef: CoefficientParams,
    signal_scale: float,
) -> float:
    """Parte sistemática de η sin intercepto ni ruido iid."""
    k = signal_scale
    f_l = math.log1p(max(lead_time_days, 0.0))
    eta = 0.0
    eta += k * coef.beta_L * f_l
    eta += k * channel_effect(channel_id, coef)
    eta += k * coef.beta_H_late * (1.0 if appointment_hour >= 15 else 0.0)
    eta += k * dow_effect(appointment_dow, coef)
    eta += k * specialty_effect(specialty_id, coef)
    eta += k * coef.beta_R * float(patient_prior_no_show_rate)
    eta += k * coef.beta_first_visit * (1.0 if patient_prior_appt_count == 0 else 0.0)
    eta += k * coef.beta_cov_particular * (1.0 if coverage_id == COVERAGE_PARTICULAR else 0.0)
    eta += k * coef.beta_rem * float(reminder_sent)
    eta += k * coef.beta_lead_x_web * f_l * (1.0 if channel_id == CHANNEL_WEB else 0.0)
    eta += float(patient_u)
    eta += float(provider_v)
    eta += seasonality(appointment_month, coef)
    return eta


def full_logit(
    systematic: float,
    beta_0: float,
    eps: float,
) -> float:
    return float(beta_0 + systematic + eps)


def probability_from_logit(eta: float, config: GeneratorConfig) -> float:
    p = float(sigmoid(eta))
    return float(clip_probability(p, config.p_clip_low, config.p_clip_high))
