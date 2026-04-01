"""Shared helpers and limits for ingestion and profiling."""

from __future__ import annotations

import re

import pandas as pd

PREVIEW_ROWS = 50
MAX_CATEGORICAL_UNIQUE = 50
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def column_name_suggests_id(name: str) -> bool:
    n = name.strip().lower().replace(" ", "_")
    if n in ("id", "idx", "uuid", "key"):
        return True
    if n.endswith("_id") or n.startswith("id_"):
        return True
    for token in ("uuid", "sku", "codigo", "code", "index"):
        if token in n and len(n) <= 24:
            return True
    return False


def memory_usage_mb(df: pd.DataFrame) -> float:
    return float(df.memory_usage(deep=True).sum() / (1024 * 1024))


def series_is_fixed_length_strings(s: pd.Series) -> bool:
    non_null = s.dropna()
    if non_null.empty:
        return False
    strs = non_null.astype(str)
    lengths = strs.str.len()
    return bool(lengths.nunique() == 1 and lengths.iloc[0] >= 4)


def series_looks_like_uuid(s: pd.Series) -> bool:
    non_null = s.dropna().astype(str)
    if non_null.empty:
        return False
    return bool(non_null.str.match(UUID_PATTERN).mean() >= 0.9)
