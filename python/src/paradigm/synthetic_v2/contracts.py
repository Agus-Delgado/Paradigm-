"""Contratos tipados del generador sintético v2 (sin I/O)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from paradigm.synthetic_v2.intervention import InterventionParams


class ScenarioId(str, Enum):
    SIGNAL_WEAK = "signal_weak"
    SIGNAL_MODERATE = "signal_moderate"
    SIGNAL_STRONG = "signal_strong"
    POLICY_INTERVENTION = "policy_intervention"


@dataclass(frozen=True)
class NoiseParams:
    sigma_u: float = 0.45
    sigma_v: float = 0.25
    sigma_eps: float = 0.35


@dataclass(frozen=True)
class CoefficientParams:
    beta_0: float = -2.1
    beta_L: float = 0.35
    beta_C_web: float = 0.40
    beta_C_phone: float = 0.15
    beta_C_reception: float = 0.0
    beta_H_late: float = 0.25
    beta_D_mon: float = 0.15
    beta_D_fri: float = 0.12
    beta_S: tuple[float, ...] = (0.05, 0.20, -0.10, 0.10, -0.15, -0.12)
    beta_R: float = 0.80
    beta_first_visit: float = 0.10
    beta_cov_particular: float = 0.20
    beta_rem: float = -0.55
    beta_lead_x_web: float = 0.20
    alpha_season_month: float = 0.12


@dataclass(frozen=True)
class GeneratorConfig:
    """Configuración completa de una generación."""

    generator_version: str = "2.2.0"
    seed: int = 42
    scenario: ScenarioId = ScenarioId.SIGNAL_MODERATE
    n_appointments: int = 2000
    n_patients: int = 180
    n_providers: int = 8
    date_start: str = "2024-01-02"
    date_end: str = "2025-12-31"
    pi_cancel: float = 0.18
    # Tasa elegible objetivo común (ATTENDED ∪ NO_SHOW)
    target_no_show_rate: float = 0.13
    # Alias histórico (misma semántica)
    target_eligible_noshow_rate: float | None = None
    signal_scale: float = 1.0
    noise: NoiseParams = field(default_factory=NoiseParams)
    reminder_base_rate: float = 0.35
    coefficients: CoefficientParams = field(default_factory=CoefficientParams)
    intervention: InterventionParams = field(default_factory=InterventionParams)
    p_clip_low: float = 0.02
    p_clip_high: float = 0.85
    calibrate_intercept: bool = True
    calibration_tolerance: float = 1e-4
    calibration_max_iterations: int = 80
    calibration_xtol: float = 1e-6
    observed_rate_z: float = 2.0
    observed_rate_tol_floor: float = 0.015
    write_row_truth: bool = True
    dataset_id: str | None = None
    output_root: str | None = None

    def __post_init__(self) -> None:
        # Congelar alias: si solo viene el histórico, usarlo como target.
        if self.target_eligible_noshow_rate is not None:
            object.__setattr__(self, "target_no_show_rate", float(self.target_eligible_noshow_rate))
        object.__setattr__(self, "target_eligible_noshow_rate", float(self.target_no_show_rate))

    def resolved_dataset_id(self) -> str:
        if self.dataset_id:
            return self.dataset_id
        return f"{self.scenario.value}_seed{self.seed}"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["scenario"] = self.scenario.value
        d["target_no_show_rate"] = self.target_no_show_rate
        d["target_eligible_noshow_rate"] = self.target_no_show_rate
        return d

    @staticmethod
    def from_dict(data: dict[str, Any]) -> GeneratorConfig:
        noise_raw = data.get("noise") or {}
        coef_raw = data.get("coefficients") or {}
        beta_s = coef_raw.get("beta_S", CoefficientParams().beta_S)
        if isinstance(beta_s, list):
            beta_s = tuple(float(x) for x in beta_s)
        scenario = data.get("scenario", ScenarioId.SIGNAL_MODERATE.value)
        if isinstance(scenario, ScenarioId):
            scenario_id = scenario
        else:
            scenario_id = ScenarioId(str(scenario))
        target = data.get("target_no_show_rate")
        if target is None:
            target = data.get("target_eligible_noshow_rate", 0.13)
        inter_raw = data.get("intervention") or {}
        intervention = InterventionParams(
            enabled=bool(inter_raw.get("enabled", False)),
            treatment_prob=float(inter_raw.get("treatment_prob", 0.5)),
            cost_per_intervention=float(inter_raw.get("cost_per_intervention", 1.0)),
            delta_base=float(inter_raw.get("delta_base", -0.35)),
            delta_lead_long=float(inter_raw.get("delta_lead_long", -0.25)),
            delta_channel_web=float(inter_raw.get("delta_channel_web", -0.20)),
            delta_channel_phone=float(inter_raw.get("delta_channel_phone", -0.05)),
            delta_channel_reception=float(inter_raw.get("delta_channel_reception", 0.0)),
            delta_hour_late=float(inter_raw.get("delta_hour_late", -0.10)),
            delta_first_visit=float(inter_raw.get("delta_first_visit", -0.15)),
            delta_repeat=float(inter_raw.get("delta_repeat", -0.05)),
            require_lead_at_least=int(inter_raw.get("require_lead_at_least", 1)),
        )
        return GeneratorConfig(
            generator_version=str(data.get("generator_version", "2.2.0")),
            seed=int(data.get("seed", 42)),
            scenario=scenario_id,
            n_appointments=int(data.get("n_appointments", 2000)),
            n_patients=int(data.get("n_patients", 180)),
            n_providers=int(data.get("n_providers", 8)),
            date_start=str(data.get("date_start", "2024-01-02")),
            date_end=str(data.get("date_end", "2025-12-31")),
            pi_cancel=float(data.get("pi_cancel", 0.18)),
            target_no_show_rate=float(target),
            signal_scale=float(data.get("signal_scale", 1.0)),
            noise=NoiseParams(
                sigma_u=float(noise_raw.get("sigma_u", 0.45)),
                sigma_v=float(noise_raw.get("sigma_v", 0.25)),
                sigma_eps=float(noise_raw.get("sigma_eps", 0.35)),
            ),
            reminder_base_rate=float(data.get("reminder_base_rate", 0.35)),
            coefficients=CoefficientParams(
                beta_0=float(coef_raw.get("beta_0", -2.1)),
                beta_L=float(coef_raw.get("beta_L", 0.35)),
                beta_C_web=float(
                    coef_raw.get(
                        "beta_C_web",
                        coef_raw.get("beta_C", {}).get("WEB", 0.40)
                        if isinstance(coef_raw.get("beta_C"), dict)
                        else 0.40,
                    )
                ),
                beta_C_phone=float(
                    coef_raw.get(
                        "beta_C_phone",
                        coef_raw.get("beta_C", {}).get("PHONE", 0.15)
                        if isinstance(coef_raw.get("beta_C"), dict)
                        else 0.15,
                    )
                ),
                beta_C_reception=float(
                    coef_raw.get(
                        "beta_C_reception",
                        coef_raw.get("beta_C", {}).get("RECEPTION", 0.0)
                        if isinstance(coef_raw.get("beta_C"), dict)
                        else 0.0,
                    )
                ),
                beta_H_late=float(coef_raw.get("beta_H_late", 0.25)),
                beta_D_mon=float(
                    coef_raw.get(
                        "beta_D_mon",
                        coef_raw.get("beta_D", {}).get("Mon", 0.15)
                        if isinstance(coef_raw.get("beta_D"), dict)
                        else 0.15,
                    )
                ),
                beta_D_fri=float(
                    coef_raw.get(
                        "beta_D_fri",
                        coef_raw.get("beta_D", {}).get("Fri", 0.12)
                        if isinstance(coef_raw.get("beta_D"), dict)
                        else 0.12,
                    )
                ),
                beta_S=tuple(float(x) for x in beta_s),
                beta_R=float(coef_raw.get("beta_R", 0.80)),
                beta_first_visit=float(coef_raw.get("beta_first_visit", 0.10)),
                beta_cov_particular=float(coef_raw.get("beta_cov_particular", 0.20)),
                beta_rem=float(coef_raw.get("beta_rem", -0.55)),
                beta_lead_x_web=float(coef_raw.get("beta_lead_x_web", 0.20)),
                alpha_season_month=float(coef_raw.get("alpha_season_month", 0.12)),
            ),
            intervention=intervention,
            p_clip_low=float(data.get("p_clip_low", (data.get("p_clip") or [0.02, 0.85])[0])),
            p_clip_high=float(data.get("p_clip_high", (data.get("p_clip") or [0.02, 0.85])[1])),
            calibrate_intercept=bool(data.get("calibrate_intercept", True)),
            calibration_tolerance=float(data.get("calibration_tolerance", 1e-4)),
            calibration_max_iterations=int(data.get("calibration_max_iterations", 80)),
            calibration_xtol=float(data.get("calibration_xtol", 1e-6)),
            observed_rate_z=float(data.get("observed_rate_z", 2.0)),
            observed_rate_tol_floor=float(data.get("observed_rate_tol_floor", 0.015)),
            write_row_truth=bool(data.get("write_row_truth", True)),
            dataset_id=data.get("dataset_id"),
            output_root=data.get("output_root"),
        )


# Column manifests (leakage / API contracts)
PREDECISIONAL_COLUMNS: tuple[str, ...] = (
    "appointment_id",
    "patient_id",
    "provider_id",
    "specialty_id",
    "coverage_id",
    "booking_channel_id",
    "appointment_date",
    "appointment_start",
    "booking_date",
    "booking_ts",
    "lead_time_days",
    "appointment_hour",
    "appointment_dow",
    "appointment_month",
    "booking_hour",
    "reminder_sent",
    "age_band",
    "sex",
    "patient_prior_appt_count",
    "patient_prior_no_show_count",
    "patient_prior_no_show_rate",
    "provider_prior_appt_count",
    "provider_prior_no_show_count",
    "provider_prior_no_show_rate",
    "is_repeat_patient",
)

TRUTH_COLUMNS: tuple[str, ...] = (
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
)

POST_OUTCOME_COLUMNS: tuple[str, ...] = (
    "appointment_status_id",
    "status_code",
    "cancellation_ts",
    "cancellation_reason_id",
)

BILLING_POST_OUTCOME_COLUMNS: tuple[str, ...] = (
    "billing_line_id",
    "billing_date",
    "line_amount",
    "billing_status_id",
    "currency",
)


@dataclass
class GeneratorTruth:
    generator_version: str
    generated_at: str
    seed: int
    scenario: str
    dataset_id: str
    coefficients: dict[str, Any]
    signal_scale: float
    noise: dict[str, float]
    interactions: list[str]
    seasonality: dict[str, float]
    patient_effects_summary: dict[str, float]
    provider_effects: dict[str, float]
    calibration: dict[str, Any]
    p_clip: list[float]
    excluded_from_features: list[str]
    predecisional_columns: list[str]
    truth_columns: list[str]
    data_fingerprint: dict[str, str]
    config_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationMetrics:
    eligible_n: int
    noshow_n: int
    noshow_rate: float
    target_rate: float
    rate_abs_error: float
    expected_rate: float | None
    expected_abs_error: float | None
    expected_rate_ok: bool
    observed_rate_tolerance: float
    observed_rate_ok: bool
    calibrated_intercept: float | None
    calibration_iterations: int | None
    calibration_converged: bool
    rate_in_soft_band: bool
    coverage_match_rate: float
    key_coverage_ok: bool
    p_min: float
    p_max: float
    p_in_range: bool
    p_never_01: bool
    leakage_columns_found: list[str]
    leakage_ok: bool
    true_p_auc: float | None
    brier_true_p: float | None
    brier_constant: float | None
    truth_config_coherent: bool
    checks_passed: bool
    intervention_enabled: bool = False
    treatment_rate: float | None = None
    ate_probability: float | None = None
    ate_outcome: float | None = None
    balance_max_abs_std_diff: float | None = None
    intervention_balance_ok: bool = True
    intervention_segment_effects: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GenerationResult:
    dataset_id: str
    output_dir: Path
    config: GeneratorConfig
    truth: GeneratorTruth
    validation: ValidationMetrics
    csv_paths: dict[str, Path]
    artifact_paths: dict[str, Path]

    def to_metadata_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "output_dir": str(self.output_dir),
            "scenario": self.config.scenario.value,
            "seed": self.config.seed,
            "generator_version": self.config.generator_version,
            "n_appointments": self.config.n_appointments,
            "csv_files": {k: v.name for k, v in self.csv_paths.items()},
            "artifacts": {k: v.name for k, v in self.artifact_paths.items()},
            "checks_passed": self.validation.checks_passed,
            "noshow_rate": self.validation.noshow_rate,
            "true_p_auc": self.validation.true_p_auc,
        }
