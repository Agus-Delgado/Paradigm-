"""Monte Carlo what-if simulator for prescriptive interventions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ml.experiments.tracker import ExperimentTracker

from .recommender import DEFAULT_INTERVENTIONS, InterventionProfile


@dataclass(frozen=True)
class SimulationConfig:
    """Runtime controls for what-if simulation."""

    iterations: int = 1000
    random_seed: int = 42
    overbooking_fill_rate: float = 0.65


def simulate_what_if(
    recommendations: pd.DataFrame,
    config: SimulationConfig | None = None,
    *,
    tracker_base_dir: Path | None = None,
    experiment_name: str = "prescriptive_what_if",
) -> dict[str, object]:
    """Estimate slots recovered and revenue impact for a recommendation set.

    Required recommendation columns:
    - predicted_proba
    - recommended_intervention

    Optional recommendation columns leveraged when available:
    - demand_pressure, revenue_per_slot_ars
    - intervention_effectiveness, intervention_uptake
    - expected_cost_ars
    """
    if recommendations.empty:
        return {
            "summary": {
                "iterations": 0,
                "slots_recovered_mean": 0.0,
                "revenue_impact_mean_ars": 0.0,
                "cost_mean_ars": 0.0,
                "net_impact_mean_ars": 0.0,
            },
            "before_after": pd.DataFrame(),
            "intervention_breakdown": pd.DataFrame(),
            "iterations": pd.DataFrame(),
            "tracker_run_dir": None,
        }

    if "predicted_proba" not in recommendations.columns:
        raise ValueError("recommendations must include 'predicted_proba'.")
    if "recommended_intervention" not in recommendations.columns:
        raise ValueError("recommendations must include 'recommended_intervention'.")

    cfg = config or SimulationConfig()
    if cfg.iterations <= 0:
        raise ValueError("SimulationConfig.iterations must be > 0.")

    frame = recommendations.copy()
    frame["predicted_proba"] = pd.to_numeric(frame["predicted_proba"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    frame["demand_pressure"] = pd.to_numeric(frame.get("demand_pressure", 1.0), errors="coerce").fillna(1.0).clip(0.5, 2.0)

    policy_map = {profile.key: profile for profile in DEFAULT_INTERVENTIONS}
    frame["revenue_per_slot_ars"] = _resolve_revenue(frame, policy_map)
    frame["effectiveness"] = _resolve_effectiveness(frame, policy_map)
    frame["uptake"] = _resolve_uptake(frame, policy_map)
    frame["cost_per_action_ars"] = _resolve_cost(frame, policy_map)

    sim_iterations = _run_monte_carlo(frame, cfg, policy_map)
    summary = _build_summary(sim_iterations, cfg.iterations)
    before_after = _build_before_after(frame, summary)
    breakdown = _build_intervention_breakdown(frame)

    tracker_run_dir = _track_simulation(
        tracker_base_dir=tracker_base_dir,
        experiment_name=experiment_name,
        config=cfg,
        recommendations=frame,
        summary=summary,
        before_after=before_after,
        breakdown=breakdown,
    )

    return {
        "summary": summary,
        "before_after": before_after,
        "intervention_breakdown": breakdown,
        "iterations": sim_iterations,
        "tracker_run_dir": tracker_run_dir,
    }


def _run_monte_carlo(
    frame: pd.DataFrame,
    cfg: SimulationConfig,
    policy_map: dict[str, InterventionProfile],
) -> pd.DataFrame:
    rng = np.random.default_rng(cfg.random_seed)
    risk = frame["predicted_proba"].to_numpy(dtype=float)
    pressure = frame["demand_pressure"].to_numpy(dtype=float)
    effectiveness = frame["effectiveness"].to_numpy(dtype=float)
    uptake_prob = frame["uptake"].to_numpy(dtype=float)
    revenue = frame["revenue_per_slot_ars"].to_numpy(dtype=float)
    action_cost = frame["cost_per_action_ars"].to_numpy(dtype=float)
    intervention_keys = frame["recommended_intervention"].astype(str).to_numpy()

    out_rows: list[dict[str, float | int]] = []
    for i in range(cfg.iterations):
        baseline_no_show = rng.random(len(frame)) < risk

        uplift_noise = rng.normal(0.0, 0.04, size=len(frame))
        realized_effectiveness = np.clip(effectiveness + uplift_noise, 0.0, 0.85)

        uptake_draw = rng.random(len(frame)) < uptake_prob
        treated_risk = np.where(
            uptake_draw,
            np.clip(risk * (1.0 - realized_effectiveness), 0.0, 1.0),
            risk,
        )
        treated_no_show = rng.random(len(frame)) < treated_risk

        avoided = baseline_no_show.astype(int) - treated_no_show.astype(int)
        base_slots_recovered = np.clip(avoided, 0, 1).astype(float)

        overbooking_bonus = np.zeros(len(frame), dtype=float)
        for idx, key in enumerate(intervention_keys):
            profile = policy_map.get(key)
            if profile is None or profile.category != "overbooking":
                continue
            fill_probability = np.clip(cfg.overbooking_fill_rate * pressure[idx], 0.0, 1.0)
            overbooking_bonus[idx] = 1.0 if rng.random() < fill_probability else 0.0

        slots_recovered = base_slots_recovered + overbooking_bonus
        revenue_impact = float(np.sum(slots_recovered * revenue))
        costs = float(np.sum(uptake_draw.astype(float) * action_cost))

        out_rows.append(
            {
                "iteration": i,
                "baseline_no_shows": int(np.sum(baseline_no_show)),
                "treated_no_shows": int(np.sum(treated_no_show)),
                "slots_recovered": float(np.sum(slots_recovered)),
                "revenue_impact_ars": revenue_impact,
                "cost_ars": costs,
                "net_impact_ars": revenue_impact - costs,
            }
        )

    return pd.DataFrame(out_rows)


def _build_summary(iterations: pd.DataFrame, n_iterations: int) -> dict[str, float | int]:
    slots = iterations["slots_recovered"]
    revenue = iterations["revenue_impact_ars"]
    costs = iterations["cost_ars"]
    net = iterations["net_impact_ars"]

    return {
        "iterations": int(n_iterations),
        "slots_recovered_mean": float(slots.mean()),
        "slots_recovered_p05": float(np.percentile(slots, 5)),
        "slots_recovered_p95": float(np.percentile(slots, 95)),
        "revenue_impact_mean_ars": float(revenue.mean()),
        "revenue_impact_p05_ars": float(np.percentile(revenue, 5)),
        "revenue_impact_p95_ars": float(np.percentile(revenue, 95)),
        "cost_mean_ars": float(costs.mean()),
        "net_impact_mean_ars": float(net.mean()),
    }


def _build_before_after(frame: pd.DataFrame, summary: dict[str, float | int]) -> pd.DataFrame:
    baseline_no_show_expected = float(frame["predicted_proba"].sum())
    treated_no_show_expected = max(
        0.0,
        baseline_no_show_expected - float(summary["slots_recovered_mean"]),
    )

    return pd.DataFrame(
        [
            {
                "scenario": "Before intervention",
                "expected_no_shows": baseline_no_show_expected,
                "expected_slots_lost": baseline_no_show_expected,
                "expected_revenue_impact_ars": 0.0,
            },
            {
                "scenario": "After intervention",
                "expected_no_shows": treated_no_show_expected,
                "expected_slots_lost": treated_no_show_expected,
                "expected_revenue_impact_ars": float(summary["revenue_impact_mean_ars"]),
            },
        ]
    )


def _build_intervention_breakdown(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        frame.groupby("recommended_intervention", as_index=False)
        .agg(
            appointments=("predicted_proba", "size"),
            avg_risk=("predicted_proba", "mean"),
            avg_effectiveness=("effectiveness", "mean"),
            avg_uptake=("uptake", "mean"),
            avg_revenue_per_slot_ars=("revenue_per_slot_ars", "mean"),
            avg_cost_per_action_ars=("cost_per_action_ars", "mean"),
        )
        .sort_values("appointments", ascending=False)
        .reset_index(drop=True)
    )
    return grouped


def _track_simulation(
    *,
    tracker_base_dir: Path | None,
    experiment_name: str,
    config: SimulationConfig,
    recommendations: pd.DataFrame,
    summary: dict[str, float | int],
    before_after: pd.DataFrame,
    breakdown: pd.DataFrame,
) -> str | None:
    if tracker_base_dir is None:
        return None

    tracker = ExperimentTracker(base_dir=tracker_base_dir)
    tracker.start_experiment(
        name=experiment_name,
        model_type="prescriptive_simulation",
        hyperparameters={
            "iterations": config.iterations,
            "random_seed": config.random_seed,
            "overbooking_fill_rate": config.overbooking_fill_rate,
            "population_size": int(len(recommendations)),
        },
        notes="What-if simulation for no-show interventions.",
    )
    tracker.log_metrics({k: v for k, v in summary.items() if isinstance(v, (int, float))})

    assert tracker.run_dir is not None
    run_dir = tracker.run_dir
    recommendations.head(500).to_csv(run_dir / "prescriptive_recommendations_sample.csv", index=False)
    before_after.to_csv(run_dir / "what_if_before_after.csv", index=False)
    breakdown.to_csv(run_dir / "intervention_breakdown.csv", index=False)

    with (run_dir / "what_if_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)

    tracker.finish_experiment(status="completed")
    return str(run_dir)


def _resolve_revenue(
    frame: pd.DataFrame,
    policy_map: dict[str, InterventionProfile],
) -> pd.Series:
    from_policy = frame["recommended_intervention"].map(
        lambda key: policy_map.get(str(key), DEFAULT_INTERVENTIONS[0]).default_revenue_per_slot_ars
    )
    from_row = pd.to_numeric(frame.get("revenue_per_slot_ars"), errors="coerce")
    return from_row.fillna(from_policy).astype(float).clip(lower=0.0)


def _resolve_effectiveness(
    frame: pd.DataFrame,
    policy_map: dict[str, InterventionProfile],
) -> pd.Series:
    from_policy = frame["recommended_intervention"].map(
        lambda key: policy_map.get(str(key), DEFAULT_INTERVENTIONS[0]).effectiveness
    )
    from_row = pd.to_numeric(frame.get("intervention_effectiveness"), errors="coerce")
    return from_row.fillna(from_policy).astype(float).clip(lower=0.0, upper=0.95)


def _resolve_uptake(
    frame: pd.DataFrame,
    policy_map: dict[str, InterventionProfile],
) -> pd.Series:
    from_policy = frame["recommended_intervention"].map(
        lambda key: policy_map.get(str(key), DEFAULT_INTERVENTIONS[0]).uptake_rate
    )
    from_row = pd.to_numeric(frame.get("intervention_uptake"), errors="coerce")
    return from_row.fillna(from_policy).astype(float).clip(lower=0.0, upper=1.0)


def _resolve_cost(
    frame: pd.DataFrame,
    policy_map: dict[str, InterventionProfile],
) -> pd.Series:
    from_policy = frame["recommended_intervention"].map(
        lambda key: policy_map.get(str(key), DEFAULT_INTERVENTIONS[0]).cost_per_action_ars
    )
    from_row = pd.to_numeric(frame.get("expected_cost_ars"), errors="coerce")
    return from_row.fillna(from_policy).astype(float).clip(lower=0.0)
