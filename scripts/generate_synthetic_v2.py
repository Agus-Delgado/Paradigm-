"""
CLI del generador sintético v2.

Ejemplo:
  python scripts/generate_synthetic_v2.py --scenario signal_moderate --seed 42
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "python" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paradigm.synthetic_v2 import ScenarioId, config_for_scenario, run_generation  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate Paradigm synthetic v2 dataset (isolated).")
    p.add_argument(
        "--scenario",
        choices=[s.value for s in ScenarioId],
        default=ScenarioId.SIGNAL_MODERATE.value,
        help="Signal/policy scenario (default: signal_moderate)",
    )
    p.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Root directory for datasets (default: data/synthetic_v2/)",
    )
    p.add_argument(
        "--dataset-id",
        type=str,
        default=None,
        help="Subfolder name under output-dir (default: <scenario>_seed<seed>)",
    )
    p.add_argument("--n-appointments", type=int, default=None, help="Override appointment count")
    p.add_argument("--n-patients", type=int, default=None, help="Override patient count")
    p.add_argument(
        "--no-calibrate-intercept",
        action="store_true",
        help="Disable beta_0 bisection calibration",
    )
    p.add_argument(
        "--treatment-prob",
        type=float,
        default=None,
        help="Override intervention treatment probability (policy_intervention)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    overrides: dict = {
        "seed": args.seed,
        "dataset_id": args.dataset_id,
        "calibrate_intercept": not args.no_calibrate_intercept,
    }
    if args.n_appointments is not None:
        overrides["n_appointments"] = args.n_appointments
    if args.n_patients is not None:
        overrides["n_patients"] = args.n_patients
    if args.output_dir is not None:
        overrides["output_root"] = str(args.output_dir.resolve())

    config = config_for_scenario(args.scenario, **overrides)
    if args.treatment_prob is not None and config.intervention.enabled:
        from dataclasses import replace

        config = replace(
            config,
            intervention=replace(config.intervention, treatment_prob=float(args.treatment_prob)),
        )
    result = run_generation(
        config,
        output_root=args.output_dir.resolve() if args.output_dir is not None else None,
    )
    v = result.validation
    print(f"Wrote dataset to {result.output_dir}")
    print(
        f"scenario={result.config.scenario.value} seed={result.config.seed} "
        f"eligible_n={v.eligible_n} noshow_rate={v.noshow_rate:.4f} "
        f"true_p_auc={v.true_p_auc} checks_passed={v.checks_passed}"
    )
    if v.intervention_enabled:
        print(
            f"intervention: treatment_rate={v.treatment_rate} "
            f"ATE_p={v.ate_probability} ATE_y={v.ate_outcome} "
            f"balance_smd={v.balance_max_abs_std_diff}"
        )
    if v.notes:
        for note in v.notes:
            print(f"note: {note}")
    return 0 if v.checks_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
