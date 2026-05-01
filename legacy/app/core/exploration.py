"""Filtros de exploración y utilidades sobre DataFrame (sin dependencia de Streamlit)."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

import pandas as pd

# Tipos lógicos que admiten filtro en esta fase (no text ni id).
FILTERABLE_LOGICAL_TYPES = frozenset({"categorical", "numeric", "boolean", "datetime"})

# Máximo de columnas con controles de filtro simultáneos (UX escalable).
MAX_FILTER_COLUMNS = 6

def filterable_columns(logical: dict[str, str], column_order: list[str]) -> list[str]:
    """Columnas elegibles para filtro, en el orden de aparición del dataset."""
    return [c for c in column_order if logical.get(c, "text") in FILTERABLE_LOGICAL_TYPES]


def pick_default_exploration_column(logical: dict[str, str], columns: list[str]) -> str:
    """Prioridad alineada al gráfico automático previo: numeric → categorical → text/boolean → primera columna."""
    for wanted in ("numeric", "categorical"):
        for col in columns:
            if logical.get(col) == wanted:
                return col
    for prefer in ("text", "boolean"):
        for col in columns:
            if logical.get(col) == prefer:
                return col
    return columns[0]


def default_chart_kind(logical_type: str) -> str:
    if logical_type == "numeric":
        return "histograma"
    if logical_type in ("categorical", "boolean"):
        return "barras"
    if logical_type == "datetime":
        return "temporal"
    return "ninguno"


def chart_kinds_for_logical_type(logical_type: str) -> list[str]:
    if logical_type == "numeric":
        return ["histograma", "boxplot"]
    if logical_type == "categorical":
        return ["barras"]
    if logical_type == "boolean":
        return ["barras"]
    if logical_type == "datetime":
        return ["temporal"]
    if logical_type in ("text", "id"):
        return ["ninguno"]
    return ["ninguno"]


def _bool_series_matches(series: pd.Series, want_true: bool) -> pd.Series:
    try:
        lower = series.astype(str).str.strip().str.lower()
    except Exception:
        return pd.Series(False, index=series.index)
    true_set = {"true", "yes", "1", "si", "sí", "t", "y"}
    false_set = {"false", "no", "0", "f", "n"}
    if want_true:
        return lower.isin(true_set)
    return lower.isin(false_set)


def build_filter_mask(df: pd.DataFrame, logical: dict[str, str], specs: dict[str, dict[str, Any]]) -> pd.Series:
    """
    specs: columna -> payload según tipo:
      categorical: {"kind": "categorical", "values": list}  (vacío = no acota)
      numeric: {"kind": "numeric", "lo": float, "hi": float}
      boolean: {"kind": "boolean", "mode": "all"|"true"|"false"}
      datetime: {"kind": "datetime", "start": date|None, "end": date|None}
    """
    mask = pd.Series(True, index=df.index)
    for col, spec in specs.items():
        if col not in df.columns:
            continue
        lt = logical.get(col, "text")
        kind = spec.get("kind")
        if kind == "categorical" and lt == "categorical":
            vals = spec.get("values") or []
            if not vals:
                continue
            str_vals = [str(v) for v in vals]
            m = df[col].notna() & df[col].astype(str).isin(str_vals)
            mask &= m

        elif kind == "numeric" and lt == "numeric":
            num = pd.to_numeric(df[col], errors="coerce")
            lo, hi = float(spec["lo"]), float(spec["hi"])
            mask &= (num.isna()) | ((num >= lo) & (num <= hi))

        elif kind == "boolean" and lt == "boolean":
            mode = spec.get("mode", "all")
            if mode == "all":
                continue
            if mode == "true":
                mask &= _bool_series_matches(df[col], True)
            elif mode == "false":
                mask &= _bool_series_matches(df[col], False)

        elif kind == "datetime" and lt == "datetime":
            dt = pd.to_datetime(df[col], errors="coerce")
            start_d = spec.get("start")
            end_d = spec.get("end")
            if start_d is not None:
                start_ts = pd.Timestamp(datetime.combine(start_d, time.min))
                mask &= (dt.isna()) | (dt >= start_ts)
            if end_d is not None:
                end_ts = pd.Timestamp(datetime.combine(end_d, time.max))
                mask &= (dt.isna()) | (dt <= end_ts)

    return mask


def count_active_specs(specs: dict[str, dict[str, Any]]) -> int:
    n = 0
    for spec in specs.values():
        kind = spec.get("kind")
        if kind == "categorical":
            if spec.get("values"):
                n += 1
        elif kind == "numeric":
            n += 1
        elif kind == "boolean":
            if spec.get("mode", "all") != "all":
                n += 1
        elif kind == "datetime":
            if spec.get("start") is not None or spec.get("end") is not None:
                n += 1
    return n
