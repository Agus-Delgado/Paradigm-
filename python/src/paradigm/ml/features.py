"""
Features conocibles al momento de la reserva + historial estrictamente anterior
(misma cita excluida). Sin estado final, cancelación ni facturación.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Columnas pasadas al ColumnTransformer (ids como categóricas)
CATEGORICAL_FEATURES = [
    "provider_id",
    "specialty_id",
    "booking_channel_id",
    "coverage_id",
    "age_band",
    "sex",
]
NUMERIC_FEATURES = [
    "lead_time_days",
    "appointment_hour",
    "appointment_dow",
    "appointment_month",
    "booking_hour",
    "patient_prior_appt_count",
    "patient_prior_no_show_count",
    "patient_prior_no_show_rate",
    "provider_prior_appt_count",
    "provider_prior_no_show_count",
    "provider_prior_no_show_rate",
]


def _sorted_key(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values(
        ["patient_id", "appointment_date", "appointment_start", "appointment_id"],
        kind="mergesort",
    )


def _provider_sorted_key(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values(
        ["provider_id", "appointment_date", "appointment_start", "appointment_id"],
        kind="mergesort",
    )


def add_historical_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Historial solo con citas anteriores en el tiempo (por paciente / por proveedor).
    `is_no_show` es el desenlace de la fila actual; no se usa como feature, solo para
    acumulados con shift(1).
    """
    out = df.copy()
    out["is_no_show_row"] = (out["status_code"] == "NO_SHOW").astype(int)

    p = _sorted_key(out)
    p = p.copy()
    p["patient_prior_appt_count"] = p.groupby("patient_id", sort=False).cumcount()
    p["patient_prior_no_show_count"] = p.groupby("patient_id", sort=False)["is_no_show_row"].transform(
        lambda s: s.shift(1).fillna(0).cumsum()
    )
    out = out.drop(
        columns=["patient_prior_appt_count", "patient_prior_no_show_count"], errors="ignore"
    ).merge(
        p[
            [
                "appointment_id",
                "patient_prior_appt_count",
                "patient_prior_no_show_count",
            ]
        ],
        on="appointment_id",
        how="left",
    )

    pr = _provider_sorted_key(out)
    pr = pr.copy()
    pr["provider_prior_appt_count"] = pr.groupby("provider_id", sort=False).cumcount()
    pr["provider_prior_no_show_count"] = pr.groupby("provider_id", sort=False)["is_no_show_row"].transform(
        lambda s: s.shift(1).fillna(0).cumsum()
    )
    out = out.drop(
        columns=["provider_prior_appt_count", "provider_prior_no_show_count"], errors="ignore"
    ).merge(
        pr[
            [
                "appointment_id",
                "provider_prior_appt_count",
                "provider_prior_no_show_count",
            ]
        ],
        on="appointment_id",
        how="left",
    )

    out["patient_prior_no_show_rate"] = np.where(
        out["patient_prior_appt_count"] > 0,
        out["patient_prior_no_show_count"] / out["patient_prior_appt_count"],
        0.0,
    )
    out["provider_prior_no_show_rate"] = np.where(
        out["provider_prior_appt_count"] > 0,
        out["provider_prior_no_show_count"] / out["provider_prior_appt_count"],
        0.0,
    )
    out = out.drop(columns=["is_no_show_row"])
    return out


def add_booking_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Calendario del turno y anticipación; horas conocidas al reservar."""
    out = df.copy()
    apt_start = pd.to_datetime(out["appointment_start"], errors="coerce")
    out["appointment_hour"] = apt_start.dt.hour.fillna(0).astype(int)
    out["appointment_dow"] = out["appointment_date"].dt.dayofweek
    out["appointment_month"] = out["appointment_date"].dt.month
    out["lead_time_days"] = (out["appointment_date"] - out["booking_date"]).dt.days.clip(lower=0)
    bts = pd.to_datetime(out["booking_ts"], errors="coerce")
    out["booking_hour"] = bts.dt.hour.fillna(0).astype(int)
    return out


def build_model_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """X, y sin columnas crudas ni leakage."""
    x = df.copy()
    y = x["target_no_show"]
    drop_cols = [
        "appointment_id",
        "appointment_date",
        "appointment_start",
        "booking_date",
        "booking_ts",
        "status_code",
        "target_no_show",
    ]
    x = x.drop(columns=[c for c in drop_cols if c in x.columns])
    return x, y


def get_feature_columns() -> tuple[list[str], list[str]]:
    return list(CATEGORICAL_FEATURES), list(NUMERIC_FEATURES)
