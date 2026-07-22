"""Pipeline compacto: segmentación + drift por ventanas temporales."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from paradigm.monitoring.clustering import (
    compare_k,
    fit_kmeans_pipeline,
    profile_segments,
    select_best_k,
    stability_ari,
)
from paradigm.monitoring.drift import drift_report_between_windows
from paradigm.monitoring.features import build_clustering_frame


def assign_temporal_windows(
    df: pd.DataFrame,
    *,
    date_col: str = "appointment_date",
    n_windows: int = 3,
) -> pd.DataFrame:
    """Parte la serie en ventanas temporales contiguas por cuantiles de fecha."""
    out = df.copy()
    dates = pd.to_datetime(out[date_col])
    out[date_col] = dates
    # n_windows segmentos por cuantiles de fecha
    edges = np.linspace(0, 1, n_windows + 1)
    # Asignar por cuantiles de la distribución de fechas
    qs = dates.quantile(edges).to_numpy()
    # Evitar bordes duplicados
    qs = np.unique(qs)
    if len(qs) < 3:
        out["time_window"] = 0
        return out
    # labels 0..n-1
    out["time_window"] = pd.cut(
        dates,
        bins=qs,
        labels=False,
        include_lowest=True,
        duplicates="drop",
    )
    out["time_window"] = out["time_window"].fillna(0).astype(int)
    return out


def run_segmentation_and_drift(
    df: pd.DataFrame,
    *,
    k_values: tuple[int, ...] = (2, 3, 4, 5),
    n_windows: int = 3,
    seed: int = 42,
    outcome_col: str = "target_no_show",
) -> dict[str, Any]:
    """
    1) Compara K en la muestra completa (predecisional).
    2) Ajusta K* y perfila segmentos.
    3) Estabilidad (ARI multi-seed).
    4) Drift entre ventana 0 (ref) y ventanas posteriores.
    """
    if outcome_col not in df.columns and "status_code" in df.columns:
        df = df.copy()
        df[outcome_col] = (df["status_code"] == "NO_SHOW").astype(int)

    # Garantiza features
    _ = build_clustering_frame(df)

    k_rows = compare_k(df, k_values=k_values, seed=seed)
    best_k = select_best_k(k_rows)
    pipe, labels = fit_kmeans_pipeline(df, n_clusters=best_k, seed=seed)
    profiles = profile_segments(df, labels, outcome_col=outcome_col)
    stability = stability_ari(df, n_clusters=best_k, seeds=(0, 1, 2, 3, 4))

    windowed = assign_temporal_windows(df, n_windows=n_windows)
    windows_meta: list[dict[str, Any]] = []
    drift_by_window: list[dict[str, Any]] = []

    for w in sorted(windowed["time_window"].unique()):
        part = windowed[windowed["time_window"] == w]
        dates = pd.to_datetime(part["appointment_date"])
        windows_meta.append(
            {
                "window": int(w),
                "n": int(len(part)),
                "date_min": str(dates.min().date()),
                "date_max": str(dates.max().date()),
                "prevalence_no_show": (
                    float(part[outcome_col].mean()) if outcome_col in part.columns else None
                ),
            }
        )

    ref = windowed[windowed["time_window"] == windows_meta[0]["window"]]
    for meta in windows_meta[1:]:
        cur = windowed[windowed["time_window"] == meta["window"]]
        report = drift_report_between_windows(ref, cur, outcome_col=outcome_col)
        # Cluster composition shift vs ref (assign with global model)
        ref_labels = pipe.predict(build_clustering_frame(ref))
        cur_labels = pipe.predict(build_clustering_frame(cur))
        ref_share = {
            int(c): float((ref_labels == c).mean()) for c in range(best_k)
        }
        cur_share = {
            int(c): float((cur_labels == c).mean()) for c in range(best_k)
        }
        report["window"] = meta["window"]
        report["date_min"] = meta["date_min"]
        report["date_max"] = meta["date_max"]
        report["cluster_share_ref"] = ref_share
        report["cluster_share_cur"] = cur_share
        report["cluster_share_l1"] = float(
            sum(abs(cur_share.get(c, 0) - ref_share.get(c, 0)) for c in range(best_k))
        )
        drift_by_window.append(report)

    # Señales principales
    top_alerts: list[str] = []
    for d in drift_by_window:
        for a in d.get("alerts") or []:
            if a not in top_alerts:
                top_alerts.append(a)

    return {
        "n": int(len(df)),
        "best_k": best_k,
        "k_comparison": k_rows,
        "stability": stability,
        "profiles": profiles,
        "labels": labels.tolist(),
        "windows": windows_meta,
        "drift_by_window": drift_by_window,
        "top_drift_alerts": top_alerts,
        "seed": seed,
        "connected_to_decisions": False,
    }
