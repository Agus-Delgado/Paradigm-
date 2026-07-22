"""Calibración determinista del intercepto beta_0 (bisección)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

import numpy as np

from paradigm.synthetic_v2.contracts import GeneratorConfig
from paradigm.synthetic_v2.probability import clip_probability, sigmoid, systematic_logit


class CalibrationError(RuntimeError):
    """No se pudo calibrar beta_0 dentro de tolerancia / iteraciones."""


@dataclass(frozen=True)
class CalibrationResult:
    beta_0: float
    target_no_show_rate: float
    expected_rate: float
    expected_abs_error: float
    iterations: int
    converged: bool
    bracket_low: float
    bracket_high: float
    method: str = "bisection"
    prior_rate_assumption: str = "stationary_target_for_repeats"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def cancel_probability(lead_time_days: float, pi_cancel: float) -> float:
    pi_c = pi_cancel + 0.02 * min(float(lead_time_days) / 60.0, 1.0)
    return float(min(max(pi_c, 0.05), 0.35))


def _gauss_hermite_nodes(n: int = 15) -> tuple[np.ndarray, np.ndarray]:
    x, w = np.polynomial.hermite.hermgauss(n)
    return np.asarray(x, dtype=float), np.asarray(w, dtype=float)


def expected_sampling_probability(
    systematic: float,
    beta_0: float,
    sigma_eps: float,
    p_clip_low: float,
    p_clip_high: float,
    *,
    nodes: np.ndarray | None = None,
    weights: np.ndarray | None = None,
) -> float:
    """E[clip(σ(β0 + systematic + ε))] con ε ~ N(0, σ²), cuadratura Gauss-Hermite."""
    eta0 = float(beta_0 + systematic)
    if sigma_eps <= 1e-12:
        return float(clip_probability(float(sigmoid(eta0)), p_clip_low, p_clip_high))
    if nodes is None or weights is None:
        nodes, weights = _gauss_hermite_nodes(15)
    # eps = √2 σ x ; densidad N(0,σ²) ↔ pesos / √π
    eps = np.sqrt(2.0) * sigma_eps * nodes
    vals = clip_probability(sigmoid(eta0 + eps), p_clip_low, p_clip_high)
    return float(np.dot(weights, vals) / np.sqrt(np.pi))


def build_calibration_design(
    skeletons_sorted: Sequence[dict[str, Any]],
    config: GeneratorConfig,
) -> list[dict[str, Any]]:
    """
    Diseño de calibración sobre covariables/latentes generados.

    Conteos previos de citas: deterministas por orden cronológico.
    Tasa previa de no-show: 0 en primera cita; en repeticiones = target (estacionaria),
    porque el label aún no existe al calibrar.
    """
    target = config.target_no_show_rate
    patient_appt: dict[int, int] = {}
    provider_appt: dict[int, int] = {}
    rows: list[dict[str, Any]] = []
    for row in skeletons_sorted:
        pid = int(row["patient_id"])
        provid = int(row["provider_id"])
        p_prior = patient_appt.get(pid, 0)
        pr_prior = provider_appt.get(provid, 0)
        p_rate = 0.0 if p_prior == 0 else float(target)
        syst = systematic_logit(
            lead_time_days=row["lead_time_days"],
            channel_id=row["booking_channel_id"],
            appointment_hour=row["appointment_hour"],
            appointment_dow=row["appointment_dow"],
            appointment_month=row["appointment_month"],
            specialty_id=row["specialty_id"],
            coverage_id=row["coverage_id"],
            reminder_sent=row["reminder_sent"],
            patient_prior_no_show_rate=p_rate,
            patient_prior_appt_count=p_prior,
            patient_u=row["patient_propensity_u"],
            provider_v=row["provider_effect_v"],
            coef=config.coefficients,
            signal_scale=config.signal_scale,
        )
        pi_c = cancel_probability(row["lead_time_days"], config.pi_cancel)
        rows.append(
            {
                "systematic": float(syst),
                "pi_cancel": pi_c,
                "eligible_weight": 1.0 - pi_c,
            }
        )
        patient_appt[pid] = p_prior + 1
        provider_appt[provid] = pr_prior + 1
    return rows


def expected_eligible_noshow_rate(
    beta_0: float,
    design: Sequence[dict[str, Any]],
    config: GeneratorConfig,
    *,
    nodes: np.ndarray | None = None,
    weights: np.ndarray | None = None,
) -> float:
    """Tasa elegible esperada: Σ w_i E[p_i] / Σ w_i, w_i = 1 - π_cancel,i."""
    if nodes is None or weights is None:
        nodes, weights = _gauss_hermite_nodes(15)
    num = 0.0
    den = 0.0
    sigma = config.noise.sigma_eps
    for row in design:
        w = float(row["eligible_weight"])
        if w <= 0:
            continue
        ep = expected_sampling_probability(
            row["systematic"],
            beta_0,
            sigma,
            config.p_clip_low,
            config.p_clip_high,
            nodes=nodes,
            weights=weights,
        )
        num += w * ep
        den += w
    if den <= 0:
        raise CalibrationError("Peso elegible total nulo; no se puede calibrar.")
    return num / den


def _expand_bracket(
    design: Sequence[dict[str, Any]],
    config: GeneratorConfig,
    target: float,
    nodes: np.ndarray,
    weights: np.ndarray,
) -> tuple[float, float, float, float]:
    lo, hi = -8.0, 4.0
    f_lo = expected_eligible_noshow_rate(lo, design, config, nodes=nodes, weights=weights) - target
    f_hi = expected_eligible_noshow_rate(hi, design, config, nodes=nodes, weights=weights) - target
    expands = 0
    while f_lo * f_hi > 0 and expands < 8:
        if abs(f_lo) < abs(f_hi):
            lo -= 2.0
            f_lo = (
                expected_eligible_noshow_rate(lo, design, config, nodes=nodes, weights=weights)
                - target
            )
        else:
            hi += 2.0
            f_hi = (
                expected_eligible_noshow_rate(hi, design, config, nodes=nodes, weights=weights)
                - target
            )
        expands += 1
    if f_lo * f_hi > 0:
        raise CalibrationError(
            f"No se pudo acotar beta_0 para target={target}: "
            f"f({lo})={f_lo:.6f}, f({hi})={f_hi:.6f}"
        )
    return lo, hi, f_lo, f_hi


def calibrate_beta0_bisection(
    skeletons_sorted: Sequence[dict[str, Any]],
    config: GeneratorConfig,
) -> CalibrationResult:
    """
    Bisección determinista de beta_0 para igualar la tasa elegible *esperada*
    (covariables + latentes + cancelación + E_ε[p_sample]) al target.
    """
    target = float(config.target_no_show_rate)
    tol = float(config.calibration_tolerance)
    xtol = float(config.calibration_xtol)
    max_iter = int(config.calibration_max_iterations)
    design = build_calibration_design(skeletons_sorted, config)
    nodes, weights = _gauss_hermite_nodes(15)

    lo, hi, f_lo, f_hi = _expand_bracket(design, config, target, nodes, weights)
    mid = 0.5 * (lo + hi)
    f_mid = expected_eligible_noshow_rate(mid, design, config, nodes=nodes, weights=weights) - target
    it = 0
    for it in range(1, max_iter + 1):
        mid = 0.5 * (lo + hi)
        rate_mid = expected_eligible_noshow_rate(
            mid, design, config, nodes=nodes, weights=weights
        )
        f_mid = rate_mid - target
        if abs(f_mid) <= tol or (hi - lo) <= xtol:
            return CalibrationResult(
                beta_0=float(mid),
                target_no_show_rate=target,
                expected_rate=float(rate_mid),
                expected_abs_error=float(abs(f_mid)),
                iterations=it,
                converged=True,
                bracket_low=float(lo),
                bracket_high=float(hi),
            )
        # Mantener cambio de signo
        if f_lo * f_mid <= 0:
            hi = mid
            f_hi = f_mid
        else:
            lo = mid
            f_lo = f_mid

    rate_final = expected_eligible_noshow_rate(mid, design, config, nodes=nodes, weights=weights)
    err = abs(rate_final - target)
    result = CalibrationResult(
        beta_0=float(mid),
        target_no_show_rate=target,
        expected_rate=float(rate_final),
        expected_abs_error=float(err),
        iterations=max_iter,
        converged=False,
        bracket_low=float(lo),
        bracket_high=float(hi),
    )
    raise CalibrationError(
        f"Bisección sin convergencia tras {max_iter} iteraciones: "
        f"expected_rate={rate_final:.6f} target={target:.6f} err={err:.6g} "
        f"bracket=[{lo:.4f},{hi:.4f}]"
    )


def observed_rate_tolerance(
    target: float,
    eligible_n: int,
    *,
    z: float = 2.0,
    floor: float = 0.015,
) -> float:
    """Tolerancia de tasa observada ~ z * SE bernoulli, con piso."""
    if eligible_n <= 0:
        return 1.0
    p = min(max(target, 1e-6), 1.0 - 1e-6)
    se = float(np.sqrt(p * (1.0 - p) / eligible_n))
    return float(max(floor, z * se))
