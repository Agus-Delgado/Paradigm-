"""Persistencia de datasets sintéticos v2 (solo bajo demanda)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

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
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def config_fingerprint(config: GeneratorConfig) -> str:
    payload = json.dumps(config.to_dict(), sort_keys=True, separators=(",", ":"))
    return sha256_bytes(payload.encode("utf-8"))


def write_frames(output_dir: Path, frames: dict[str, pd.DataFrame]) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, df in frames.items():
        path = output_dir / f"{name}.csv"
        df.to_csv(path, index=False)
        paths[name] = path
    return paths


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def build_truth(
    *,
    config: GeneratorConfig,
    generated_at: str,
    dataset_id: str,
    frames: dict[str, pd.DataFrame],
    csv_paths: dict[str, Path],
    calibration: dict[str, Any],
) -> GeneratorTruth:
    patients = frames["latent_patient_effects"]
    providers = frames["latent_provider_effects"]
    coef = config.coefficients
    fingerprint = {name: sha256_file(path) for name, path in sorted(csv_paths.items())}
    return GeneratorTruth(
        generator_version=config.generator_version,
        generated_at=generated_at,
        seed=config.seed,
        scenario=config.scenario.value,
        dataset_id=dataset_id,
        coefficients={
            "beta_0": coef.beta_0,
            "beta_L": coef.beta_L,
            "beta_C": {
                "WEB": coef.beta_C_web,
                "PHONE": coef.beta_C_phone,
                "RECEPTION": coef.beta_C_reception,
            },
            "beta_H_late": coef.beta_H_late,
            "beta_D": {"Mon": coef.beta_D_mon, "Fri": coef.beta_D_fri},
            "beta_S": list(coef.beta_S),
            "beta_R": coef.beta_R,
            "beta_first_visit": coef.beta_first_visit,
            "beta_cov_particular": coef.beta_cov_particular,
            "beta_rem": coef.beta_rem,
            "beta_lead_x_web": coef.beta_lead_x_web,
            "alpha_season_month": coef.alpha_season_month,
        },
        signal_scale=config.signal_scale,
        noise={
            "sigma_u": config.noise.sigma_u,
            "sigma_v": config.noise.sigma_v,
            "sigma_eps": config.noise.sigma_eps,
        },
        interactions=["lead_x_web"],
        seasonality={"alpha_season_month": coef.alpha_season_month},
        patient_effects_summary={
            "mean": float(patients["patient_propensity_u"].mean()),
            "std": float(patients["patient_propensity_u"].std(ddof=0)),
            "n": int(len(patients)),
        },
        provider_effects={
            str(int(r.provider_id)): float(r.provider_effect_v)
            for r in providers.itertuples()
        },
        calibration=calibration,
        p_clip=[config.p_clip_low, config.p_clip_high],
        excluded_from_features=list(POST_OUTCOME_COLUMNS)
        + list(TRUTH_COLUMNS)
        + list(INTERVENTION_ASSIGNMENT_COLUMNS)
        + list(INTERVENTION_TRUTH_COLUMNS)
        + [
            "billing_line_id",
            "billing_date",
            "line_amount",
            "billing_status_id",
            "currency",
        ],
        predecisional_columns=list(PREDECISIONAL_COLUMNS),
        truth_columns=list(TRUTH_COLUMNS) + list(INTERVENTION_TRUTH_COLUMNS),
        data_fingerprint=fingerprint,
        config_fingerprint=config_fingerprint(config),
    )


def write_artifacts(
    output_dir: Path,
    *,
    config: GeneratorConfig,
    truth: GeneratorTruth,
    validation: ValidationMetrics,
    metadata: dict[str, Any],
) -> dict[str, Path]:
    paths = {
        "generator_config": write_json(output_dir / "generator_config.json", config.to_dict()),
        "generator_truth": write_json(output_dir / "generator_truth.json", truth.to_dict()),
        "validation_metrics": write_json(
            output_dir / "validation_metrics.json", validation.to_dict()
        ),
        "generation_metadata": write_json(output_dir / "generation_metadata.json", metadata),
    }
    return paths
