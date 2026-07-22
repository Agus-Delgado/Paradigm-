"""Orquestación: generar → persistir → validar."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from paradigm.io.paths import REPO_ROOT
from paradigm.synthetic_v2.contracts import GenerationResult, GeneratorConfig
from paradigm.synthetic_v2.generate import generate_dataset
from paradigm.synthetic_v2.persist import build_truth, write_artifacts, write_frames
from paradigm.synthetic_v2.validate import validate_generation


def default_output_root() -> Path:
    return REPO_ROOT / "data" / "synthetic_v2"


def run_generation(
    config: GeneratorConfig,
    *,
    output_root: Path | None = None,
) -> GenerationResult:
    """
    Genera un dataset bajo data/synthetic_v2/<dataset_id>/ (o output_root override).
    No toca data/synthetic/.
    Falla con CalibrationError si el solver de intercepto no converge.
    """
    root = output_root
    if root is None:
        if config.output_root:
            root = Path(config.output_root)
        else:
            root = default_output_root()
    dataset_id = config.resolved_dataset_id()
    output_dir = Path(root) / dataset_id

    generated = generate_dataset(config)
    frames = generated["frames"]
    config_used: GeneratorConfig = generated["config_used"]
    calibration = generated["calibration"]

    csv_paths = write_frames(output_dir, frames)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    elig = frames["fact_appointment"][
        frames["fact_appointment"]["status_code"].isin(["ATTENDED", "NO_SHOW"])
    ]
    observed_rate = float((elig["status_code"] == "NO_SHOW").mean()) if len(elig) else float("nan")

    calibration_block = {
        **calibration.to_dict(),
        "calibrated_intercept": calibration.beta_0,
        "observed_rate": observed_rate,
        "observed_abs_error": abs(observed_rate - config_used.target_no_show_rate)
        if len(elig)
        else float("nan"),
        "eligible_n": int(len(elig)),
        "noshow_n": int((elig["status_code"] == "NO_SHOW").sum()) if len(elig) else 0,
        "calibrate_intercept": config_used.calibrate_intercept,
        "calibration_tolerance": config_used.calibration_tolerance,
        "calibration_max_iterations": config_used.calibration_max_iterations,
        "calibration_xtol": config_used.calibration_xtol,
    }

    prelim_truth = build_truth(
        config=config_used,
        generated_at=generated_at,
        dataset_id=dataset_id,
        frames=frames,
        csv_paths=csv_paths,
        calibration=calibration_block,
    )
    validation = validate_generation(frames=frames, config=config_used, truth=prelim_truth)
    calibration_block["true_p_auc"] = validation.true_p_auc

    truth = build_truth(
        config=config_used,
        generated_at=generated_at,
        dataset_id=dataset_id,
        frames=frames,
        csv_paths=csv_paths,
        calibration=calibration_block,
    )
    validation = validate_generation(frames=frames, config=config_used, truth=truth)

    metadata = {
        "dataset_id": dataset_id,
        "output_dir": str(output_dir),
        "generated_at": generated_at,
        "scenario": config_used.scenario.value,
        "seed": config_used.seed,
        "generator_version": config_used.generator_version,
        "n_appointments": config_used.n_appointments,
        "n_patients": config_used.n_patients,
        "n_providers": config_used.n_providers,
        "checks_passed": validation.checks_passed,
        "noshow_rate": validation.noshow_rate,
        "expected_rate": validation.expected_rate,
        "true_p_auc": validation.true_p_auc,
        "calibrated_intercept": validation.calibrated_intercept,
        "calibration_converged": validation.calibration_converged,
        "legacy_synthetic_untouched": True,
        "legacy_path": "data/synthetic/",
    }
    artifact_paths = write_artifacts(
        output_dir,
        config=config_used,
        truth=truth,
        validation=validation,
        metadata=metadata,
    )
    return GenerationResult(
        dataset_id=dataset_id,
        output_dir=output_dir,
        config=config_used,
        truth=truth,
        validation=validation,
        csv_paths=csv_paths,
        artifact_paths=artifact_paths,
    )
