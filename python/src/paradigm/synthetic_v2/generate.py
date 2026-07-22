"""Generación reproducible de entidades sintéticas v2 (en memoria)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from paradigm.synthetic_v2.calibrate import (
    CalibrationResult,
    calibrate_beta0_bisection,
    cancel_probability,
)
from paradigm.synthetic_v2.contracts import GeneratorConfig
from paradigm.synthetic_v2.intervention import (
    assign_treatment,
    treatment_logit_delta,
)
from paradigm.synthetic_v2.probability import (
    CHANNEL_PHONE,
    CHANNEL_RECEPTION,
    CHANNEL_WEB,
    full_logit,
    probability_from_logit,
    systematic_logit,
)

STATUS_ATTENDED = 1
STATUS_CANCELLED = 2
STATUS_NO_SHOW = 3

SPECIALTY_NAMES = [
    "Clínica médica",
    "Cardiología",
    "Dermatología",
    "Pediatría",
    "Ginecología",
    "Traumatología",
]

COVERAGE_NAMES = [
    "OSDE",
    "Swiss Medical",
    "Galeno",
    "PAMI",
    "Sancor Salud",
    "Particular",
]


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def build_dimension_frames(config: GeneratorConfig) -> dict[str, pd.DataFrame]:
    dr = pd.date_range(config.date_start, config.date_end, freq="D")
    dim_date = pd.DataFrame(
        [
            {
                "date_key": int(d.strftime("%Y%m%d")),
                "date": d.date().isoformat(),
                "year": d.year,
                "month": d.month,
                "iso_week": int(d.isocalendar()[1]),
                "day_of_week": d.isoweekday(),
            }
            for d in dr
        ]
    )
    return {
        "dim_date": dim_date,
        "dim_specialty": pd.DataFrame(
            {"specialty_id": range(1, 7), "specialty_name": SPECIALTY_NAMES}
        ),
        "dim_coverage": pd.DataFrame(
            {"coverage_id": range(1, 7), "coverage_name": COVERAGE_NAMES}
        ),
        "dim_appointment_status": pd.DataFrame(
            {
                "appointment_status_id": [1, 2, 3],
                "status_code": ["ATTENDED", "CANCELLED", "NO_SHOW"],
                "status_description": ["Atendida", "Cancelada", "No-show"],
            }
        ),
        "dim_booking_channel": pd.DataFrame(
            {
                "booking_channel_id": [CHANNEL_WEB, CHANNEL_PHONE, CHANNEL_RECEPTION],
                "channel_code": ["WEB", "PHONE", "RECEPTION"],
                "channel_name": ["Web / app", "Telefónico", "Recepción"],
            }
        ),
        "dim_billing_status": pd.DataFrame(
            {
                "billing_status_id": [1, 2, 3, 4],
                "status_code": ["ISSUED", "PENDING", "VOID", "PAID"],
                "status_description": [
                    "Facturado emitido",
                    "Pendiente de facturación",
                    "Anulado",
                    "Pagado (proxy)",
                ],
            }
        ),
        "dim_cancellation_reason": pd.DataFrame(
            {
                "cancellation_reason_id": [1, 2, 3, 4],
                "reason_code": ["PATIENT", "SCHEDULE", "ADMIN", "OTHER"],
                "reason_description": [
                    "Paciente solicitó",
                    "Cambio de agenda del centro",
                    "Motivo administrativo",
                    "Otro / no informado",
                ],
            }
        ),
    }


def sample_patients(rng: np.random.Generator, config: GeneratorConfig) -> pd.DataFrame:
    n = config.n_patients
    u = rng.normal(0.0, config.noise.sigma_u, size=n)
    return pd.DataFrame(
        {
            "patient_id": np.arange(1, n + 1),
            "age_band": rng.choice(
                ["18-34", "35-54", "55-69", "70+"], size=n, p=[0.28, 0.38, 0.24, 0.10]
            ),
            "sex": rng.choice(["F", "M", "X"], size=n, p=[0.52, 0.46, 0.02]),
            "coverage_id": rng.integers(1, 7, size=n),
            "patient_propensity_u": u,
        }
    )


def sample_providers(rng: np.random.Generator, config: GeneratorConfig) -> pd.DataFrame:
    n = config.n_providers
    # Misma asignación primaria que v1 para n=8; genérica si cambia n.
    if n == 8:
        primary = np.array([1, 1, 2, 3, 4, 5, 6, 2], dtype=int)
    else:
        primary = 1 + (np.arange(n) % 6)
    v = rng.normal(0.0, config.noise.sigma_v, size=n)
    return pd.DataFrame(
        {
            "provider_id": np.arange(1, n + 1),
            "provider_label": [f"PR-{i:02d}" for i in range(1, n + 1)],
            "primary_specialty_id": primary,
            "provider_effect_v": v,
        }
    )


def _sample_skeletons(
    rng: np.random.Generator,
    config: GeneratorConfig,
    patients: pd.DataFrame,
    providers: pd.DataFrame,
) -> list[dict[str, Any]]:
    business_days = pd.bdate_range(config.date_start, config.date_end)
    channel_weights = np.array([0.35, 0.40, 0.25])
    primary = providers.set_index("provider_id")["primary_specialty_id"].to_dict()
    cov_by_patient = patients.set_index("patient_id")["coverage_id"].to_dict()
    age_by_patient = patients.set_index("patient_id")["age_band"].to_dict()
    sex_by_patient = patients.set_index("patient_id")["sex"].to_dict()
    u_by_patient = patients.set_index("patient_id")["patient_propensity_u"].to_dict()
    v_by_provider = providers.set_index("provider_id")["provider_effect_v"].to_dict()

    rows: list[dict[str, Any]] = []
    for i in range(config.n_appointments):
        apt_num = i + 1
        appointment_id = f"APT-{apt_num:05d}"
        d = business_days[int(rng.integers(0, len(business_days)))]
        day = d.date()
        hour = int(rng.integers(8, 18))
        minute = int(rng.choice([0, 15, 30, 45]))
        appointment_start = datetime.combine(day, datetime.min.time()) + timedelta(
            hours=hour, minutes=minute
        )
        pid = int(rng.integers(1, config.n_patients + 1))
        prov_id = int(rng.integers(1, config.n_providers + 1))
        specialty_id = int(primary[prov_id])
        cov_id = int(cov_by_patient[pid])
        channel_id = int(rng.choice([CHANNEL_WEB, CHANNEL_PHONE, CHANNEL_RECEPTION], p=channel_weights))
        lead_days = int(min(60, max(0, round(float(rng.gamma(2.5, 5.0))))))
        booking_ts = appointment_start - timedelta(days=lead_days)
        while booking_ts.weekday() >= 5:
            booking_ts += timedelta(days=1)
        booking_ts = booking_ts.replace(
            hour=int(rng.integers(9, 19)),
            minute=int(rng.choice([0, 15, 30])),
            second=0,
            microsecond=0,
        )
        # lead efectivo tras ajuste de fin de semana
        lead_eff = max(0, (appointment_start.date() - booking_ts.date()).days)
        reminder_sent = 0
        if lead_eff >= 1 and rng.random() < config.reminder_base_rate:
            reminder_sent = 1

        rows.append(
            {
                "appointment_id": appointment_id,
                "patient_id": pid,
                "provider_id": prov_id,
                "specialty_id": specialty_id,
                "coverage_id": cov_id,
                "booking_channel_id": channel_id,
                "appointment_date": day.isoformat(),
                "appointment_start": _iso(appointment_start),
                "booking_date": booking_ts.date().isoformat(),
                "booking_ts": _iso(booking_ts),
                "lead_time_days": lead_eff,
                "appointment_hour": hour,
                "appointment_dow": appointment_start.weekday(),
                "appointment_month": appointment_start.month,
                "booking_hour": booking_ts.hour,
                "reminder_sent": reminder_sent,
                "age_band": age_by_patient[pid],
                "sex": sex_by_patient[pid],
                "patient_propensity_u": float(u_by_patient[pid]),
                "provider_effect_v": float(v_by_provider[prov_id]),
                "_appointment_start_dt": appointment_start,
                "_booking_ts_dt": booking_ts,
            }
        )
    return rows


def _assign_outcomes(
    rng: np.random.Generator,
    skeletons_sorted: list[dict[str, Any]],
    config: GeneratorConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], CalibrationResult]:
    if config.calibrate_intercept:
        calibration = calibrate_beta0_bisection(skeletons_sorted, config)
        beta_0 = calibration.beta_0
    else:
        beta_0 = config.coefficients.beta_0
        calibration = CalibrationResult(
            beta_0=float(beta_0),
            target_no_show_rate=float(config.target_no_show_rate),
            expected_rate=float("nan"),
            expected_abs_error=float("nan"),
            iterations=0,
            converged=True,
            bracket_low=float(beta_0),
            bracket_high=float(beta_0),
            method="disabled",
        )

    patient_hist: dict[int, list[int]] = {}
    provider_hist: dict[int, list[int]] = {}
    appointments: list[dict[str, Any]] = []
    billing_lines: list[dict[str, Any]] = []
    line_counter = 1
    status_map = {1: "ATTENDED", 2: "CANCELLED", 3: "NO_SHOW"}

    for row in skeletons_sorted:
        pid = row["patient_id"]
        provid = row["provider_id"]
        p_hist = patient_hist.get(pid, [])
        pr_hist = provider_hist.get(provid, [])
        patient_prior_appt = len(p_hist)
        patient_prior_ns = int(sum(p_hist))
        provider_prior_appt = len(pr_hist)
        provider_prior_ns = int(sum(pr_hist))
        patient_prior_rate = (
            patient_prior_ns / patient_prior_appt if patient_prior_appt > 0 else 0.0
        )
        provider_prior_rate = (
            provider_prior_ns / provider_prior_appt if provider_prior_appt > 0 else 0.0
        )

        syst = systematic_logit(
            lead_time_days=row["lead_time_days"],
            channel_id=row["booking_channel_id"],
            appointment_hour=row["appointment_hour"],
            appointment_dow=row["appointment_dow"],
            appointment_month=row["appointment_month"],
            specialty_id=row["specialty_id"],
            coverage_id=row["coverage_id"],
            reminder_sent=row["reminder_sent"],
            patient_prior_no_show_rate=patient_prior_rate,
            patient_prior_appt_count=patient_prior_appt,
            patient_u=row["patient_propensity_u"],
            provider_v=row["provider_effect_v"],
            coef=config.coefficients,
            signal_scale=config.signal_scale,
        )
        # Verdad conocida = propensión sistemática (sin ε).
        # ε solo perturba la probabilidad de muestreo para controlar dificultad.
        eps = float(rng.normal(0.0, config.noise.sigma_eps))
        eta0 = full_logit(syst, beta_0, 0.0)
        p0 = probability_from_logit(eta0, config)
        p0_sample = probability_from_logit(full_logit(syst, beta_0, eps), config)

        is_repeat = int(patient_prior_appt > 0)
        intervention_on = bool(config.intervention.enabled)
        t = 0
        delta = 0.0
        eta1 = eta0
        p1 = p0
        p1_sample = p0_sample
        if intervention_on:
            t = assign_treatment(
                rng=rng,
                lead_time_days=row["lead_time_days"],
                params=config.intervention,
            )
            delta = treatment_logit_delta(
                lead_time_days=row["lead_time_days"],
                channel_id=row["booking_channel_id"],
                appointment_hour=row["appointment_hour"],
                is_repeat_patient=is_repeat,
                params=config.intervention,
            )
            eta1 = full_logit(syst + delta, beta_0, 0.0)
            p1 = probability_from_logit(eta1, config)
            p1_sample = probability_from_logit(full_logit(syst + delta, beta_0, eps), config)

        cancellation_ts = ""
        cancel_reason_id: int | str = ""
        pi_c = cancel_probability(row["lead_time_days"], config.pi_cancel)
        true_y0: int | str = ""
        true_y1: int | str = ""
        true_ite: int | str = ""
        if rng.random() < pi_c:
            status_id = STATUS_CANCELLED
            cancel_reason_id = int(rng.integers(1, 5))
            appt_start = row["_appointment_start_dt"]
            book_ts = row["_booking_ts_dt"]
            if rng.random() < 0.35:
                delta_h = float(rng.uniform(0.5, 23.0))
                c_ts = appt_start - timedelta(hours=delta_h)
                if c_ts < book_ts:
                    c_ts = book_ts + timedelta(hours=1)
            else:
                span = max((appt_start - book_ts).total_seconds() - 3600, 3600.0)
                offset = float(rng.uniform(0, span))
                c_ts = book_ts + timedelta(seconds=offset)
                if c_ts >= appt_start:
                    c_ts = appt_start - timedelta(hours=2)
            cancellation_ts = _iso(c_ts)
        elif intervention_on:
            # Potential outcomes acoplados con el mismo U ~ Unif
            u = float(rng.random())
            y0 = int(u < p0_sample)
            y1 = int(u < p1_sample)
            true_y0 = y0
            true_y1 = y1
            true_ite = int(y1 - y0)
            y_obs = y1 if t == 1 else y0
            status_id = STATUS_NO_SHOW if y_obs == 1 else STATUS_ATTENDED
        elif rng.random() < p0_sample:
            status_id = STATUS_NO_SHOW
        else:
            status_id = STATUS_ATTENDED

        # Historial solo para elegibles (ATTENDED / NO_SHOW), como el modelo
        if status_id in (STATUS_ATTENDED, STATUS_NO_SHOW):
            y = 1 if status_id == STATUS_NO_SHOW else 0
            patient_hist.setdefault(pid, []).append(y)
            provider_hist.setdefault(provid, []).append(y)

        if t == 1:
            eta_obs, p_obs = eta1, p1
        else:
            eta_obs, p_obs = eta0, p0

        intervention_cost = (
            float(config.intervention.cost_per_intervention) if t == 1 else 0.0
        )

        out = {
            "appointment_id": row["appointment_id"],
            "patient_id": pid,
            "provider_id": provid,
            "specialty_id": row["specialty_id"],
            "coverage_id": row["coverage_id"],
            "booking_channel_id": row["booking_channel_id"],
            "appointment_date": row["appointment_date"],
            "appointment_start": row["appointment_start"],
            "booking_date": row["booking_date"],
            "booking_ts": row["booking_ts"],
            "lead_time_days": row["lead_time_days"],
            "appointment_hour": row["appointment_hour"],
            "appointment_dow": row["appointment_dow"],
            "appointment_month": row["appointment_month"],
            "booking_hour": row["booking_hour"],
            "reminder_sent": row["reminder_sent"],
            "extra_reminder": int(t),
            "intervention_cost": intervention_cost,
            "age_band": row["age_band"],
            "sex": row["sex"],
            "patient_prior_appt_count": patient_prior_appt,
            "patient_prior_no_show_count": patient_prior_ns,
            "patient_prior_no_show_rate": round(patient_prior_rate, 6),
            "provider_prior_appt_count": provider_prior_appt,
            "provider_prior_no_show_count": provider_prior_ns,
            "provider_prior_no_show_rate": round(provider_prior_rate, 6),
            "is_repeat_patient": is_repeat,
            "true_logit": round(eta_obs, 8),
            "true_no_show_probability": round(p_obs, 8),
            "true_logit_t0": round(eta0, 8),
            "true_logit_t1": round(eta1, 8),
            "true_p0": round(p0, 8),
            "true_p1": round(p1, 8),
            "true_ite_probability": round(float(p1 - p0), 8),
            "true_y0": true_y0,
            "true_y1": true_y1,
            "true_ite": true_ite,
            "patient_propensity_u": round(row["patient_propensity_u"], 8),
            "provider_effect_v": round(row["provider_effect_v"], 8),
            "appointment_status_id": status_id,
            "status_code": status_map[status_id],
            "cancellation_ts": cancellation_ts,
            "cancellation_reason_id": cancel_reason_id,
        }
        appointments.append(out)

        # Facturación post-outcome
        day = datetime.fromisoformat(row["appointment_date"]).date()
        if status_id == STATUS_ATTENDED:
            if rng.random() >= 0.06:
                n_lines = int(rng.choice([1, 2], p=[0.82, 0.18]))
                for _ in range(n_lines):
                    amt = float(rng.uniform(6500, 28000))
                    bstat = int(rng.choice([1, 2, 4], p=[0.42, 0.18, 0.40]))
                    delay_days = int(rng.integers(0, 5))
                    bdate = (day + timedelta(days=delay_days)).isoformat()
                    if bstat == 2:
                        bdate = day.isoformat()
                    billing_lines.append(
                        {
                            "billing_line_id": f"BLN-{line_counter:05d}",
                            "appointment_id": row["appointment_id"],
                            "billing_date": bdate,
                            "line_amount": round(amt, 2),
                            "billing_status_id": bstat,
                            "currency": "ARS",
                        }
                    )
                    line_counter += 1
        elif status_id == STATUS_NO_SHOW and rng.random() < 0.12:
            billing_lines.append(
                {
                    "billing_line_id": f"BLN-{line_counter:05d}",
                    "appointment_id": row["appointment_id"],
                    "billing_date": day.isoformat(),
                    "line_amount": round(float(rng.uniform(2000, 5000)), 2),
                    "billing_status_id": 2,
                    "currency": "ARS",
                }
            )
            line_counter += 1

    return appointments, billing_lines, calibration


def generate_dataset(config: GeneratorConfig) -> dict[str, Any]:
    """
    Genera frames en memoria. No escribe disco.
    Orden RNG: patients → providers → skeletons → (calibración sin RNG) → outcomes/billing.
    """
    rng = np.random.default_rng(config.seed)
    dims = build_dimension_frames(config)
    patients = sample_patients(rng, config)
    providers = sample_providers(rng, config)
    skeletons = _sample_skeletons(rng, config, patients, providers)
    skeletons_sorted = sorted(
        skeletons,
        key=lambda r: (r["appointment_date"], r["appointment_start"], r["appointment_id"]),
    )
    appointments, billing_lines, calibration = _assign_outcomes(rng, skeletons_sorted, config)
    beta_0_used = calibration.beta_0

    config_used = replace(
        config,
        coefficients=replace(config.coefficients, beta_0=beta_0_used),
    )

    dim_patient = patients.drop(columns=["patient_propensity_u"])
    dim_provider = providers.drop(columns=["provider_effect_v"])
    # Latentes también en tablas auxiliares de verdad
    latent_patient = patients[["patient_id", "patient_propensity_u"]].copy()
    latent_provider = providers[["provider_id", "provider_effect_v"]].copy()

    fact_appointment = pd.DataFrame(appointments)
    fact_billing = pd.DataFrame(billing_lines)
    if fact_billing.empty:
        fact_billing = pd.DataFrame(
            columns=[
                "billing_line_id",
                "appointment_id",
                "billing_date",
                "line_amount",
                "billing_status_id",
                "currency",
            ]
        )

    frames = {
        **dims,
        "dim_patient": dim_patient,
        "dim_provider": dim_provider,
        "fact_appointment": fact_appointment,
        "fact_billing_line": fact_billing,
        "latent_patient_effects": latent_patient,
        "latent_provider_effects": latent_provider,
    }
    if config.write_row_truth:
        truth_cols = [
            "appointment_id",
            "true_logit",
            "true_no_show_probability",
            "patient_propensity_u",
            "provider_effect_v",
            "true_logit_t0",
            "true_logit_t1",
            "true_p0",
            "true_p1",
            "true_ite_probability",
            "true_y0",
            "true_y1",
            "true_ite",
            "extra_reminder",
            "intervention_cost",
        ]
        frames["appointment_truth"] = fact_appointment[
            [c for c in truth_cols if c in fact_appointment.columns]
        ].copy()

    return {
        "frames": frames,
        "config_used": config_used,
        "beta_0_used": beta_0_used,
        "calibration": calibration,
    }
