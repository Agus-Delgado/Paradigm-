"""Configuración económica y de política del motor prescriptivo."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


SUPPORTED_POLICIES: tuple[str, ...] = (
    "none",
    "treat_all",
    "random",
    "risk",
    "uplift",
    "net_value",
)


@dataclass(frozen=True)
class PrescriptiveConfig:
    """Parámetros del Decide layer (no-show)."""

    benefit_per_avoided: float = 10.0
    intervention_cost: float = 0.4
    max_interventions: int | None = 30
    max_intervention_fraction: float | None = 0.2
    min_net_value: float = 0.0
    random_seed: int = 42

    # Calidad estimada del ranking uplift en [0, 1] (proxy; no reentrena).
    uplift_quality: float = 0.0
    uplift_quality_threshold: float = 0.75

    # ATE de referencia cuando no hay uplift por cita (gate económico).
    assumed_ate: float = 0.055

    # Forzar política (comparación / tests); None → regla automática.
    forced_policy: str | None = None

    # Columna de riesgo preferida si hay varias.
    risk_column: str = "proba_random_forest"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def resolved_capacity(self, n: int) -> int | None:
        import numpy as np

        caps: list[int] = []
        if self.max_interventions is not None:
            caps.append(int(self.max_interventions))
        if self.max_intervention_fraction is not None:
            caps.append(max(1, int(np.floor(float(self.max_intervention_fraction) * n))))
        if not caps:
            return None
        return int(min(caps))
