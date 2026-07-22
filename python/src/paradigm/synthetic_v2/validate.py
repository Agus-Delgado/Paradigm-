"""Validaciones automáticas del dataset sintético v2."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

from paradigm.synthetic_v2.calibrate import observed_rate_tolerance
from paradigm.synthetic_v2.contracts import (
    POST_OUTCOME_COLUMNS,
    PREDECISIONAL_COLUMNS,
    TRUTH_COLUMNS,
    GeneratorConfig,
    GeneratorTruth,
    ValidationMetrics,
)
from paradigm.synthetic_v2.intervention import (
    INTERVENTION_ASSIGNMENT_COLUMNS,
    INTERVENTION_TRUTH_COLUMNS,
    segment_labels,
)


def _eligible(fact: pd.DataFrame) -> pd.DataFrame:
    return fact[fact["status_code"].isin(["ATTENDED", "NO_SHOW"])].copy()


def _std_mean_diff(x_t: np.ndarray, x_c: np.ndarray) -> float:
    if len(x_t) == 0 or len(x_c) == 0:
        return float("nan")
    pooled = np.sqrt(0.5 * (np.var(x_t) + np.var(x_c)))
    if pooled < 1e-12:
        return 0.0
    return float((np.mean(x_t) - np.mean(x_c)) / pooled)


def validate_intervention_block(
    elig: pd.DataFrame,
    config: GeneratorConfig,
) -> dict[str, Any]:
    """Balance, ATE y CATE verdaderos (solo si intervention.enabled)."""
    if not config.intervention.enabled:
        return {
            "intervention_enabled": False,
            "treatment_rate": None,
            "ate_probability": None,
            "ate_outcome": None,
            "balance_max_abs_std_diff": None,
            "intervention_balance_ok": True,
            "intervention_segment_effects": {},
            "intervention_checks_passed": True,
        }

    if "extra_reminder" not in elig.columns or "true_ite_probability" not in elig.columns:
        return {
            "intervention_enabled": True,
            "treatment_rate": None,
            "ate_probability": None,
            "ate_outcome": None,
            "balance_max_abs_std_diff": None,
            "intervention_balance_ok": False,
            "intervention_segment_effects": {},
            "intervention_checks_passed": False,
        }

    t = elig["extra_reminder"].astype(int)
    treatment_rate = float(t.mean())
    target_p = float(config.intervention.treatment_prob)
    # Elegibles con lead>=1 son los asignables; tasa observada cerca de pi * P(lead ok)
    balance_ok = abs(treatment_rate - target_p) < 0.12 or treatment_rate > 0.15

    treated = elig[t == 1]
    control = elig[t == 0]
    smds = []
    for col in ("lead_time_days", "appointment_hour", "is_repeat_patient"):
        if col in elig.columns and len(treated) and len(control):
            smds.append(
                abs(
                    _std_mean_diff(
                        treated[col].to_numpy(dtype=float),
                        control[col].to_numpy(dtype=float),
                    )
                )
            )
    balance_max = float(max(smds)) if smds else 0.0
    balance_ok = balance_ok and balance_max < 0.35

    ate_p = float(elig["true_ite_probability"].astype(float).mean())
    y0 = pd.to_numeric(elig["true_y0"], errors="coerce")
    y1 = pd.to_numeric(elig["true_y1"], errors="coerce")
    ate_y = float((y1 - y0).mean())

    # Segment CATE on probability scale
    seg_effects: dict[str, list[dict[str, Any]]] = {}
    tmp = elig.copy()
    labels = [
        segment_labels(
            lead_time_days=float(r.lead_time_days),
            channel_id=int(r.booking_channel_id),
            appointment_hour=int(r.appointment_hour),
            is_repeat_patient=int(r.is_repeat_patient),
        )
        for r in tmp.itertuples()
    ]
    for key in ("lead_bin", "channel", "hour_bin", "recurrence"):
        tmp[key] = [lab[key] for lab in labels]
        rows = []
        for seg, g in tmp.groupby(key):
            rows.append(
                {
                    "segment": str(seg),
                    "n": int(len(g)),
                    "ate_probability": float(g["true_ite_probability"].mean()),
                    "treatment_rate": float(g["extra_reminder"].mean()),
                }
            )
        rows.sort(key=lambda r: r["ate_probability"])
        seg_effects[key] = rows

    # Leakage: intervention truth/assignment must not be predecisional risk features
    leak = sorted(
        set(PREDECISIONAL_COLUMNS)
        & (set(INTERVENTION_TRUTH_COLUMNS) | set(INTERVENTION_ASSIGNMENT_COLUMNS) | set(TRUTH_COLUMNS))
    )
    leak_ok = len(leak) == 0

    checks = balance_ok and leak_ok and ate_p < 0  # treatment should reduce no-show risk on average
    return {
        "intervention_enabled": True,
        "treatment_rate": treatment_rate,
        "ate_probability": ate_p,
        "ate_outcome": ate_y,
        "balance_max_abs_std_diff": balance_max,
        "intervention_balance_ok": balance_ok,
        "intervention_segment_effects": seg_effects,
        "intervention_checks_passed": checks,
        "intervention_leakage_overlap": leak,
    }


def validate_generation(
    *,
    frames: dict[str, pd.DataFrame],
    config: GeneratorConfig,
    truth: GeneratorTruth,
) -> ValidationMetrics:
    fact = frames["fact_appointment"]
    notes: list[str] = []
    cal = truth.calibration or {}

    elig = _eligible(fact)
    eligible_n = int(len(elig))
    noshow_n = int((elig["status_code"] == "NO_SHOW").sum())
    noshow_rate = float(noshow_n / eligible_n) if eligible_n else float("nan")
    target = float(config.target_no_show_rate)
    rate_err = abs(noshow_rate - target) if eligible_n else float("nan")

    expected_rate = cal.get("expected_rate")
    expected_abs_error = cal.get("expected_abs_error")
    if expected_rate is not None:
        expected_rate = float(expected_rate)
    if expected_abs_error is None and expected_rate is not None:
        expected_abs_error = abs(expected_rate - target)
    if expected_abs_error is not None:
        expected_abs_error = float(expected_abs_error)

    expected_rate_ok = bool(
        expected_rate is not None
        and expected_abs_error is not None
        and expected_abs_error <= float(config.calibration_tolerance)
        and bool(cal.get("converged", False))
    )
    if not config.calibrate_intercept:
        expected_rate_ok = True
    elif not expected_rate_ok:
        notes.append(
            "Tasa esperada fuera de tolerancia estricta o calibración no convergida."
        )

    obs_tol = observed_rate_tolerance(
        target,
        eligible_n,
        z=float(config.observed_rate_z),
        floor=float(config.observed_rate_tol_floor),
    )
    observed_rate_ok = bool(eligible_n > 0 and rate_err <= obs_tol)
    if config.intervention.enabled:
        # El tratamiento reduce la prevalencia observada respecto del target de control.
        observed_rate_ok = bool(eligible_n > 0 and 0.05 <= noshow_rate <= 0.30)
        if abs(rate_err) > obs_tol:
            notes.append(
                "Con intervención activa, la tasa observada puede desviarse del target de control; "
                f"obs={noshow_rate:.4f} target_control={target:.4f}."
            )
    elif not observed_rate_ok:
        notes.append(
            f"Tasa observada {noshow_rate:.4f} fuera de tolerancia muestral "
            f"±{obs_tol:.4f} vs target {target:.4f}."
        )

    rate_in_soft_band = bool(0.08 <= noshow_rate <= 0.25 and rate_err <= 0.05)

    patients = frames["dim_patient"].set_index("patient_id")["coverage_id"]
    merged = fact["patient_id"].map(patients)
    coverage_match_rate = float((merged == fact["coverage_id"]).mean())
    key_coverage_ok = bool(
        fact["appointment_id"].is_unique
        and fact["patient_id"].between(1, config.n_patients).all()
        and fact["provider_id"].between(1, config.n_providers).all()
        and coverage_match_rate >= 0.99
    )

    p = fact["true_no_show_probability"].astype(float)
    p_min, p_max = float(p.min()), float(p.max())
    p_in_range = bool(
        (p >= config.p_clip_low - 1e-12).all() and (p <= config.p_clip_high + 1e-12).all()
    )
    p_never_01 = bool(((p > 0.0) & (p < 1.0)).all())

    leakage = sorted(set(PREDECISIONAL_COLUMNS) & set(POST_OUTCOME_COLUMNS))
    leakage_columns_found = sorted(set(leakage))
    leakage_ok = len(leakage_columns_found) == 0
    if any(c.startswith("billing_") or c == "line_amount" for c in fact.columns):
        leakage_columns_found = sorted(
            set(leakage_columns_found) | {"billing_in_fact_appointment"}
        )
        leakage_ok = False

    true_p_auc: float | None = None
    brier_tp: float | None = None
    brier_const: float | None = None
    if eligible_n >= 10 and noshow_n > 0 and noshow_n < eligible_n:
        y = (elig["status_code"] == "NO_SHOW").astype(int).to_numpy()
        scores = elig["true_no_show_probability"].astype(float).to_numpy()
        true_p_auc = float(roc_auc_score(y, scores))
        brier_tp = float(brier_score_loss(y, scores))
        brier_const = float(brier_score_loss(y, np.full_like(scores, noshow_rate, dtype=float)))
    else:
        notes.append("AUC/Brier omitidos por falta de ambas clases en elegibles.")

    calibrated_intercept = cal.get("calibrated_intercept", cal.get("beta_0"))
    if calibrated_intercept is not None:
        calibrated_intercept = float(calibrated_intercept)
    calibration_iterations = cal.get("iterations")
    if calibration_iterations is not None:
        calibration_iterations = int(calibration_iterations)
    calibration_converged = bool(cal.get("converged", False))
    if not config.calibrate_intercept:
        calibration_converged = True

    truth_config_coherent = bool(
        truth.seed == config.seed
        and truth.scenario == config.scenario.value
        and truth.generator_version == config.generator_version
        and abs(truth.signal_scale - config.signal_scale) < 1e-12
        and abs(truth.coefficients.get("beta_0", 0) - config.coefficients.beta_0) < 1e-9
    )

    structural_ok = (
        key_coverage_ok
        and p_in_range
        and p_never_01
        and leakage_ok
        and truth_config_coherent
        and eligible_n > 0
        and expected_rate_ok
        and observed_rate_ok
        and calibration_converged
    )

    inter = validate_intervention_block(elig, config)
    if inter.get("intervention_enabled") and not inter.get("intervention_checks_passed"):
        notes.append("Validación de intervención (balance/ATE/leakage) falló.")
        structural_ok = False

    # Leakage: columnas de intervención no deben estar en manifiesto predecisional
    inter_leak = sorted(
        set(PREDECISIONAL_COLUMNS)
        & (set(INTERVENTION_TRUTH_COLUMNS) | set(INTERVENTION_ASSIGNMENT_COLUMNS))
    )
    if inter_leak:
        leakage_columns_found = sorted(set(leakage_columns_found) | set(inter_leak))
        leakage_ok = False
        structural_ok = False

    return ValidationMetrics(
        eligible_n=eligible_n,
        noshow_n=noshow_n,
        noshow_rate=noshow_rate,
        target_rate=target,
        rate_abs_error=rate_err,
        expected_rate=expected_rate,
        expected_abs_error=expected_abs_error,
        expected_rate_ok=expected_rate_ok,
        observed_rate_tolerance=obs_tol,
        observed_rate_ok=observed_rate_ok,
        calibrated_intercept=calibrated_intercept,
        calibration_iterations=calibration_iterations,
        calibration_converged=calibration_converged,
        rate_in_soft_band=rate_in_soft_band,
        coverage_match_rate=coverage_match_rate,
        key_coverage_ok=key_coverage_ok,
        p_min=p_min,
        p_max=p_max,
        p_in_range=p_in_range,
        p_never_01=p_never_01,
        leakage_columns_found=leakage_columns_found,
        leakage_ok=leakage_ok,
        true_p_auc=true_p_auc,
        brier_true_p=brier_tp,
        brier_constant=brier_const,
        truth_config_coherent=truth_config_coherent,
        checks_passed=structural_ok,
        intervention_enabled=bool(inter.get("intervention_enabled")),
        treatment_rate=inter.get("treatment_rate"),
        ate_probability=inter.get("ate_probability"),
        ate_outcome=inter.get("ate_outcome"),
        balance_max_abs_std_diff=inter.get("balance_max_abs_std_diff"),
        intervention_balance_ok=bool(inter.get("intervention_balance_ok", True)),
        intervention_segment_effects=inter.get("intervention_segment_effects") or {},
        notes=notes,
    )


def fingerprint_frames(frames: dict[str, pd.DataFrame]) -> dict[str, str]:
    """Hash determinístico del contenido tabular (orden de columnas + CSV buffer)."""
    import hashlib

    out: dict[str, str] = {}
    for name, df in sorted(frames.items()):
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        out[name] = hashlib.sha256(csv_bytes).hexdigest()
    return out


def evaluate_multiseed(
    seeds: list[int],
    *,
    n_appointments: int = 800,
    n_patients: int = 100,
) -> dict[str, Any]:
    """Evalúa prevalencia/AUC en varios seeds (en memoria; sin escribir disco)."""
    from paradigm.synthetic_v2.defaults import config_for_scenario
    from paradigm.synthetic_v2.generate import generate_dataset

    scenarios = ("signal_weak", "signal_moderate", "signal_strong")
    per_scenario: dict[str, dict[str, list[float]]] = {
        s: {"rate": [], "auc": []} for s in scenarios
    }
    order_ok = 0
    details: list[dict[str, Any]] = []

    for seed in seeds:
        row: dict[str, Any] = {"seed": seed}
        aucs: list[float] = []
        rates: list[float] = []
        for scenario in scenarios:
            cfg = config_for_scenario(
                scenario,
                seed=seed,
                n_appointments=n_appointments,
                n_patients=n_patients,
            )
            gen = generate_dataset(cfg)
            fact = gen["frames"]["fact_appointment"]
            elig = _eligible(fact)
            rate = float((elig["status_code"] == "NO_SHOW").mean())
            y = (elig["status_code"] == "NO_SHOW").astype(int).to_numpy()
            scores = elig["true_no_show_probability"].astype(float).to_numpy()
            auc = float(roc_auc_score(y, scores)) if y.min() != y.max() else float("nan")
            per_scenario[scenario]["rate"].append(rate)
            per_scenario[scenario]["auc"].append(auc)
            row[f"{scenario}_rate"] = rate
            row[f"{scenario}_auc"] = auc
            rates.append(rate)
            aucs.append(auc)
        ordered = bool(aucs[0] < aucs[1] < aucs[2])
        if ordered:
            order_ok += 1
        row["auc_order_ok"] = ordered
        row["rate_spread"] = float(max(rates) - min(rates))
        details.append(row)

    summary: dict[str, Any] = {
        "n_seeds": len(seeds),
        "seeds": list(seeds),
        "order_ok_count": order_ok,
        "order_ok_pct": float(order_ok / len(seeds)) if seeds else 0.0,
        "scenarios": {},
        "details": details,
    }
    for scenario, vals in per_scenario.items():
        r = np.asarray(vals["rate"], dtype=float)
        a = np.asarray(vals["auc"], dtype=float)
        summary["scenarios"][scenario] = {
            "rate_mean": float(r.mean()),
            "rate_std": float(r.std(ddof=0)),
            "auc_mean": float(np.nanmean(a)),
            "auc_std": float(np.nanstd(a)),
        }
    return summary
