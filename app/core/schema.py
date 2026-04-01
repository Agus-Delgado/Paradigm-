"""Infer logical column types (numeric, categorical, boolean, datetime, text, id)."""

from __future__ import annotations

import pandas as pd

from core.utils import (
    MAX_CATEGORICAL_UNIQUE,
    column_name_suggests_id,
    series_is_fixed_length_strings,
    series_looks_like_uuid,
)

BOOL_TRUE = {"true", "false", "yes", "no", "1", "0", "si", "sí", "t", "f", "y", "n"}
BOOL_MAX_UNIQUE = 4
DATETIME_YEAR_MIN = 1900
DATETIME_YEAR_MAX = 2100


def infer_logical_types(df: pd.DataFrame) -> dict[str, str]:
    return {col: _infer_column_type(df[col], col) for col in df.columns}


def _infer_column_type(series: pd.Series, name: str) -> str:
    s = series
    n = len(s)
    if n == 0:
        return "text"

    non_null = s.dropna()
    n_non_null = len(non_null)

    if _is_boolean_like(non_null):
        return "boolean"

    if _is_datetime_like(s):
        return "datetime"

    if _is_id_column(s, name, non_null):
        return "id"

    num = pd.to_numeric(s, errors="coerce")
    numeric_ratio = float(num.notna().sum()) / max(n_non_null, 1) if n_non_null else 0.0
    if numeric_ratio >= 0.85 and pd.api.types.is_numeric_dtype(num):
        return "numeric"

    uniq = non_null.nunique()
    card = uniq / max(n_non_null, 1) if n_non_null else 0.0

    if uniq <= MAX_CATEGORICAL_UNIQUE and card <= 0.6:
        return "categorical"

    return "text"


def _is_boolean_like(non_null: pd.Series) -> bool:
    if non_null.empty:
        return False
    uniq = non_null.nunique()
    if uniq > BOOL_MAX_UNIQUE:
        return False
    try:
        lower = non_null.astype(str).str.strip().str.lower()
    except Exception:
        return False
    return bool(lower.isin(BOOL_TRUE).all())


def _is_datetime_like(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    non_null = series.dropna()
    if non_null.empty:
        return False
    if pd.api.types.is_numeric_dtype(non_null):
        return False

    parsed = pd.to_datetime(series, errors="coerce", utc=False)
    ok = int(parsed.notna().sum())
    if ok / max(len(non_null), 1) < 0.7:
        return False

    valid = parsed.dropna()
    if valid.empty:
        return False

    try:
        years = valid.dt.year
        if int(years.min()) < DATETIME_YEAR_MIN or int(years.max()) > DATETIME_YEAR_MAX:
            return False
    except (AttributeError, TypeError, ValueError):
        return False

    return True


def _is_id_column(series: pd.Series, name: str, non_null: pd.Series) -> bool:
    n_non_null = len(non_null)
    if n_non_null == 0:
        return False

    uniq = non_null.nunique()
    all_non_null_unique = uniq == n_non_null

    name_ok = column_name_suggests_id(name)
    if name_ok and all_non_null_unique:
        return True

    if all_non_null_unique and (series_looks_like_uuid(non_null) or series_is_fixed_length_strings(non_null)):
        return True

    return False
