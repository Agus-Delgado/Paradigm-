"""Clustering KMeans: comparación de K, silhouette, estabilidad, perfiles."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.pipeline import Pipeline

from paradigm.monitoring.features import build_clustering_frame, make_preprocess


def fit_kmeans_pipeline(
    df: pd.DataFrame,
    *,
    n_clusters: int,
    seed: int = 42,
) -> tuple[Pipeline, np.ndarray]:
    """Ajusta preprocess+KMeans y devuelve labels."""
    x = build_clustering_frame(df)
    pipe = Pipeline(
        [
            ("prep", make_preprocess()),
            (
                "kmeans",
                KMeans(
                    n_clusters=int(n_clusters),
                    random_state=int(seed),
                    n_init=10,
                ),
            ),
        ]
    )
    labels = pipe.fit_predict(x)
    return pipe, np.asarray(labels, dtype=int)


def compare_k(
    df: pd.DataFrame,
    *,
    k_values: tuple[int, ...] = (2, 3, 4, 5, 6),
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Silhouette medio por K (muestra hasta 2000 filas para silhouette si n grande)."""
    x = build_clustering_frame(df)
    rows: list[dict[str, Any]] = []
    for k in k_values:
        if k < 2 or k >= len(x):
            continue
        pipe, labels = fit_kmeans_pipeline(df, n_clusters=k, seed=seed)
        emb = pipe.named_steps["prep"].transform(x)
        if len(x) > 2000:
            rng = np.random.default_rng(seed)
            idx = rng.choice(len(x), size=2000, replace=False)
            sil = float(silhouette_score(emb[idx], labels[idx]))
        else:
            sil = float(silhouette_score(emb, labels))
        sizes = {int(c): int((labels == c).sum()) for c in sorted(np.unique(labels))}
        rows.append(
            {
                "k": int(k),
                "silhouette": sil,
                "inertia": float(pipe.named_steps["kmeans"].inertia_),
                "cluster_sizes": sizes,
            }
        )
    rows.sort(key=lambda r: -r["silhouette"])
    return rows


def select_best_k(k_rows: list[dict[str, Any]]) -> int:
    if not k_rows:
        raise ValueError("No hay resultados de compare_k")
    return int(max(k_rows, key=lambda r: float(r["silhouette"]))["k"])


def stability_ari(
    df: pd.DataFrame,
    *,
    n_clusters: int,
    seeds: tuple[int, ...] = (0, 1, 2, 3, 4),
) -> dict[str, Any]:
    """
    Estabilidad: ARI medio entre pares de seeds (mismo dato, distinta init).

    También reporta ARI medio entre bootstrap samples (mismo seed de KMeans).
    """
    labels_by_seed: dict[int, np.ndarray] = {}
    for s in seeds:
        _, labels = fit_kmeans_pipeline(df, n_clusters=n_clusters, seed=s)
        labels_by_seed[int(s)] = labels

    pair_aris: list[float] = []
    seed_list = list(labels_by_seed.keys())
    for i in range(len(seed_list)):
        for j in range(i + 1, len(seed_list)):
            pair_aris.append(
                float(
                    adjusted_rand_score(
                        labels_by_seed[seed_list[i]],
                        labels_by_seed[seed_list[j]],
                    )
                )
            )

    # Bootstrap: 3 resamples
    boot_aris: list[float] = []
    rng = np.random.default_rng(42)
    n = len(df)
    base_labels = labels_by_seed[seed_list[0]]
    for b in range(3):
        idx = rng.choice(n, size=n, replace=True)
        sub = df.iloc[idx].reset_index(drop=True)
        _, lab = fit_kmeans_pipeline(sub, n_clusters=n_clusters, seed=seed_list[0])
        # Comparar labels del bootstrap contra base en índices muestreados
        boot_aris.append(float(adjusted_rand_score(base_labels[idx], lab)))

    mean_seed_ari = float(np.mean(pair_aris)) if pair_aris else 0.0
    mean_boot_ari = float(np.mean(boot_aris)) if boot_aris else 0.0
    return {
        "n_clusters": int(n_clusters),
        "seeds": list(seeds),
        "pairwise_seed_ari": pair_aris,
        "mean_seed_ari": mean_seed_ari,
        "bootstrap_ari": boot_aris,
        "mean_bootstrap_ari": mean_boot_ari,
        "stable": bool(mean_seed_ari >= 0.7),
    }


def profile_segments(
    df: pd.DataFrame,
    labels: np.ndarray,
    *,
    outcome_col: str | None = "target_no_show",
) -> list[dict[str, Any]]:
    """Perfil descriptivo por cluster (outcome solo para reporte, no entra al fit)."""
    frame = df.copy()
    frame["_cluster"] = np.asarray(labels, dtype=int)
    profiles: list[dict[str, Any]] = []
    for c in sorted(frame["_cluster"].unique()):
        g = frame[frame["_cluster"] == c]
        row: dict[str, Any] = {
            "cluster": int(c),
            "n": int(len(g)),
            "share": float(len(g) / max(len(frame), 1)),
        }
        if "lead_time_days" in g.columns:
            row["mean_lead_time_days"] = float(g["lead_time_days"].mean())
        if "appointment_hour" in g.columns:
            row["mean_appointment_hour"] = float(g["appointment_hour"].mean())
        if "is_repeat_patient" in g.columns:
            row["share_repeat"] = float(g["is_repeat_patient"].astype(float).mean())
        if "booking_channel_id" in g.columns:
            row["mode_booking_channel_id"] = int(g["booking_channel_id"].mode().iloc[0])
        if "specialty_id" in g.columns:
            row["mode_specialty_id"] = int(g["specialty_id"].mode().iloc[0])
        if "age_band" in g.columns:
            row["mode_age_band"] = str(g["age_band"].mode().iloc[0])
        if outcome_col and outcome_col in g.columns:
            row["prevalence_no_show"] = float(g[outcome_col].astype(float).mean())
        profiles.append(row)
    return profiles
