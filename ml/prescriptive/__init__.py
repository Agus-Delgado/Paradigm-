"""Decide (UI what-if): recomendaciones + simulación Monte Carlo para Streamlit.

Distinto del motor headless `paradigm.prescriptive` (política riesgo/uplift/ENV).
Ver `docs/FINAL_ARCHITECTURE.md`.
"""

from .exporting import (
    export_prescriptive_package_zip,
    export_recommendations_to_csv,
    generate_executive_report_md,
)
from .recommender import InterventionProfile, recommend_interventions
from .simulator import SimulationConfig, simulate_what_if

__all__ = [
    "InterventionProfile",
    "SimulationConfig",
    "export_prescriptive_package_zip",
    "export_recommendations_to_csv",
    "generate_executive_report_md",
    "recommend_interventions",
    "simulate_what_if",
]
