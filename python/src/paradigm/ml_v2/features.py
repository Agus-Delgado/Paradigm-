"""Features predecisionales para no-show v2 (sin truth / latentes / post-outcome)."""

from __future__ import annotations

import pandas as pd

from paradigm.synthetic_v2.contracts import (
    POST_OUTCOME_COLUMNS,
    TRUTH_COLUMNS,
)
from paradigm.synthetic_v2.intervention import (
    INTERVENTION_ASSIGNMENT_COLUMNS,
    INTERVENTION_TRUTH_COLUMNS,
)

# Alineado al modelo v1 + reminder / recurrencia disponibles en synthetic_v2.
PREDECISIONAL_CATEGORICAL: list[str] = [
    "provider_id",
    "specialty_id",
    "booking_channel_id",
    "coverage_id",
    "age_band",
    "sex",
]

PREDECISIONAL_NUMERIC: list[str] = [
    "lead_time_days",
    "appointment_hour",
    "appointment_dow",
    "appointment_month",
    "booking_hour",
    "reminder_sent",
    "is_repeat_patient",
    "patient_prior_appt_count",
    "patient_prior_no_show_count",
    "patient_prior_no_show_rate",
    "provider_prior_appt_count",
    "provider_prior_no_show_count",
    "provider_prior_no_show_rate",
]

# Identificadores / timestamps usados para split o join, nunca como features.
META_COLUMNS: tuple[str, ...] = (
    "appointment_id",
    "patient_id",
    "appointment_date",
    "appointment_start",
    "booking_date",
    "booking_ts",
    "target_no_show",
    "status_code",
)

FORBIDDEN_FEATURE_COLUMNS: tuple[str, ...] = tuple(
    dict.fromkeys(
        list(TRUTH_COLUMNS)
        + list(POST_OUTCOME_COLUMNS)
        + list(INTERVENTION_ASSIGNMENT_COLUMNS)
        + list(INTERVENTION_TRUTH_COLUMNS)
        + [
            "true_logit",
            "true_no_show_probability",
            "patient_propensity_u",
            "provider_effect_v",
            "appointment_status_id",
            "cancellation_ts",
            "cancellation_reason_id",
            "billing_line_id",
            "billing_date",
            "line_amount",
            "billing_status_id",
            "currency",
            "extra_reminder",
            "intervention_cost",
        ]
    )
)


def assert_no_leakage(columns: list[str] | pd.Index) -> None:
    present = sorted(set(columns) & set(FORBIDDEN_FEATURE_COLUMNS))
    if present:
        raise ValueError(f"Leakage: columnas prohibidas en el feature set: {present}")


def build_model_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """X, y solo con columnas predecisionales."""
    missing_cat = [c for c in PREDECISIONAL_CATEGORICAL if c not in df.columns]
    missing_num = [c for c in PREDECISIONAL_NUMERIC if c not in df.columns]
    if missing_cat or missing_num:
        raise KeyError(f"Faltan features: cat={missing_cat} num={missing_num}")

    feature_cols = PREDECISIONAL_CATEGORICAL + PREDECISIONAL_NUMERIC
    assert_no_leakage(feature_cols)
    x = df[feature_cols].copy()
    assert_no_leakage(x.columns)
    y = df["target_no_show"].astype(int)
    return x, y


def get_feature_columns() -> tuple[list[str], list[str]]:
    return list(PREDECISIONAL_CATEGORICAL), list(PREDECISIONAL_NUMERIC)
