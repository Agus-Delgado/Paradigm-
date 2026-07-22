"""Segmentación (clustering) y monitoreo de drift — compacto, sin decisiones."""

from __future__ import annotations

from paradigm.monitoring.clustering import (
    compare_k,
    fit_kmeans_pipeline,
    profile_segments,
    stability_ari,
)
from paradigm.monitoring.drift import (
    drift_report_between_windows,
    prevalence_drift,
)
from paradigm.monitoring.pipeline import run_segmentation_and_drift

__all__ = [
    "compare_k",
    "drift_report_between_windows",
    "fit_kmeans_pipeline",
    "prevalence_drift",
    "profile_segments",
    "run_segmentation_and_drift",
    "stability_ari",
]
