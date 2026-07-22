"""Carga de citas elegibles desde un dataset synthetic_v2 (CSV)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from paradigm.io.paths import REPO_ROOT

DEFAULT_SYNTHETIC_V2_ROOT = REPO_ROOT / "data" / "synthetic_v2"


def resolve_dataset_dir(dataset_id: str, *, data_root: Path | None = None) -> Path:
    root = Path(data_root) if data_root is not None else DEFAULT_SYNTHETIC_V2_ROOT
    path = root / dataset_id
    if not path.is_dir():
        raise FileNotFoundError(f"Dataset v2 no encontrado: {path}")
    return path


def load_eligible_v2(
    dataset_id: str,
    *,
    data_root: Path | None = None,
) -> pd.DataFrame:
    """
    Carga fact_appointment elegible (ATTENDED | NO_SHOW) desde synthetic_v2.

    Conserva columnas de truth solo para métricas de referencia; el entrenamiento
    las excluye vía el feature set de ``ml_v2.features``.
    """
    dataset_dir = resolve_dataset_dir(dataset_id, data_root=data_root)
    fact_path = dataset_dir / "fact_appointment.csv"
    if not fact_path.is_file():
        raise FileNotFoundError(f"Falta fact_appointment.csv en {dataset_dir}")

    df = pd.read_csv(fact_path)
    df = df[df["status_code"].isin(["ATTENDED", "NO_SHOW"])].copy()
    if df.empty:
        raise ValueError(f"Sin filas elegibles en {fact_path}")

    df["appointment_date"] = pd.to_datetime(df["appointment_date"])
    df["booking_date"] = pd.to_datetime(df["booking_date"])
    df["target_no_show"] = (df["status_code"] == "NO_SHOW").astype(int)
    return df.reset_index(drop=True)
