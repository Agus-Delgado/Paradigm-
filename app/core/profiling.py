"""Build dataset-level and per-column profiles."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from core.utils import memory_usage_mb


@dataclass
class ColumnProfile:
    name: str
    pandas_dtype: str
    logical_type: str
    null_count: int
    null_pct: float
    unique_count: int
    cardinality: float
    extra: str = ""


@dataclass
class DatasetProfile:
    row_count: int
    column_count: int
    total_nulls: int
    null_pct: float
    duplicate_rows: int
    memory_mb: float
    columns: list[ColumnProfile] = field(default_factory=list)


def build_profile(df: pd.DataFrame, logical_types: dict[str, str]) -> DatasetProfile:
    rows, cols = df.shape
    total_cells = rows * cols
    nulls = int(df.isna().sum().sum())
    null_pct = (nulls / total_cells * 100.0) if total_cells else 0.0
    dups = int(df.duplicated().sum())
    mem = memory_usage_mb(df)

    column_profiles: list[ColumnProfile] = []
    for name in df.columns:
        s = df[name]
        lt = logical_types.get(name, "text")
        column_profiles.append(_profile_column(s, name, lt, rows))

    return DatasetProfile(
        row_count=rows,
        column_count=cols,
        total_nulls=nulls,
        null_pct=null_pct,
        duplicate_rows=dups,
        memory_mb=mem,
        columns=column_profiles,
    )


def _extra_numeric(num: pd.Series) -> str:
    clean = num.dropna()
    if clean.empty:
        return "—"
    return (
        f"min={clean.min():g}, max={clean.max():g}, mean={clean.mean():g}, "
        f"median={clean.median():g}, std={clean.std():g}"
    )


def _profile_column(series: pd.Series, name: str, logical_type: str, row_count: int) -> ColumnProfile:
    null_count = int(series.isna().sum())
    null_pct = (null_count / row_count * 100.0) if row_count else 0.0
    non_null = series.dropna()
    unique_count = int(non_null.nunique())
    cardinality = (unique_count / len(non_null)) if len(non_null) else 0.0

    if logical_type == "numeric":
        num = pd.to_numeric(series, errors="coerce")
        extra = _extra_numeric(num)
    else:
        extra = _extra_for_type(series, logical_type, non_null)

    return ColumnProfile(
        name=name,
        pandas_dtype=str(series.dtype),
        logical_type=logical_type,
        null_count=null_count,
        null_pct=null_pct,
        unique_count=unique_count,
        cardinality=cardinality,
        extra=extra,
    )


def _extra_for_type(series: pd.Series, logical_type: str, non_null: pd.Series) -> str:
    if non_null.empty:
        return "—"

    if logical_type == "categorical":
        vc = non_null.astype(str).value_counts().head(5)
        parts = [f"{k!r}: {v}" for k, v in vc.items()]
        return "top: " + "; ".join(parts)

    if logical_type == "boolean":
        vc = non_null.astype(str).str.lower().value_counts()
        return ", ".join(f"{k}: {v}" for k, v in vc.items())

    if logical_type == "datetime":
        dt = pd.to_datetime(series, errors="coerce").dropna()
        if dt.empty:
            return "—"
        return f"min={dt.min()}, max={dt.max()}"

    if logical_type == "id":
        return "posible identificador"

    if logical_type == "text":
        strs = non_null.astype(str)
        mean_len = strs.str.len().mean()
        max_len = int(strs.str.len().max())
        return f"long. media {mean_len:.0f}, max {max_len}"

    return "—"


def profiles_to_dataframe(profile: DatasetProfile) -> pd.DataFrame:
    rows = []
    for c in profile.columns:
        rows.append(
            {
                "columna": c.name,
                "dtype pandas": c.pandas_dtype,
                "tipo inferido": c.logical_type,
                "nulos": c.null_count,
                "% nulos": round(c.null_pct, 2),
                "únicos": c.unique_count,
                "cardinalidad": round(c.cardinality, 4),
                "detalle": c.extra,
            }
        )
    return pd.DataFrame(rows)
