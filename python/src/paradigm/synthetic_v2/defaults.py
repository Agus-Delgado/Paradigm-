"""Defaults y factory de configuración por escenario."""

from __future__ import annotations

from dataclasses import replace

from paradigm.synthetic_v2.contracts import (
    CoefficientParams,
    GeneratorConfig,
    NoiseParams,
    ScenarioId,
)


def default_moderate_config(**overrides: object) -> GeneratorConfig:
    """Configuración base = escenario signal_moderate."""
    cfg = GeneratorConfig(
        scenario=ScenarioId.SIGNAL_MODERATE,
        signal_scale=1.0,
        noise=NoiseParams(sigma_u=0.45, sigma_v=0.25, sigma_eps=0.35),
        coefficients=CoefficientParams(),
    )
    if not overrides:
        return cfg
    return replace(cfg, **overrides)  # type: ignore[arg-type]


def config_for_scenario(
    scenario: ScenarioId | str,
    *,
    seed: int = 42,
    **overrides: object,
) -> GeneratorConfig:
    """Devuelve GeneratorConfig con escala/ruido del escenario de señal."""
    if isinstance(scenario, str):
        scenario = ScenarioId(scenario)

    base = default_moderate_config(seed=seed, scenario=scenario)

    if scenario == ScenarioId.SIGNAL_WEAK:
        # Señal débil: κ bajo + más ruido de muestreo (ε no entra en true_p persistida).
        base = replace(
            base,
            signal_scale=0.35,
            noise=NoiseParams(sigma_u=0.35, sigma_v=0.20, sigma_eps=0.85),
        )
    elif scenario == ScenarioId.SIGNAL_MODERATE:
        base = replace(
            base,
            signal_scale=1.0,
            noise=NoiseParams(sigma_u=0.45, sigma_v=0.25, sigma_eps=0.35),
        )
    elif scenario == ScenarioId.SIGNAL_STRONG:
        base = replace(
            base,
            signal_scale=1.8,
            noise=NoiseParams(sigma_u=0.55, sigma_v=0.30, sigma_eps=0.08),
        )
    elif scenario == ScenarioId.POLICY_INTERVENTION:
        from paradigm.synthetic_v2.intervention import InterventionParams

        # Base = señal moderada + RCT sintético de recordatorio adicional.
        base = replace(
            base,
            signal_scale=1.0,
            noise=NoiseParams(sigma_u=0.45, sigma_v=0.25, sigma_eps=0.35),
            intervention=InterventionParams(enabled=True, treatment_prob=0.5),
        )
    else:
        raise ValueError(f"Escenario no soportado aún: {scenario}")

    if overrides:
        base = replace(base, **overrides)  # type: ignore[arg-type]
    return base
