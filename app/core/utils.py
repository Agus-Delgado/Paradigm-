"""Shared helpers and limits for ingestion and profiling."""

from __future__ import annotations

import re

import pandas as pd

PREVIEW_ROWS = 50
# Vista previa en exploración: tope de filas y semilla para muestra aleatoria estable.
PREVIEW_ROWS_MAX = 200
PREVIEW_SAMPLE_RANDOM_STATE = 42
MAX_CATEGORICAL_UNIQUE = 50

# Umbrales heurísticos (resumen ejecutivo y hallazgos)
NULL_GLOBAL_QUALITY_HIGH_PCT = 10.0
NULL_GLOBAL_QUALITY_MED_PCT = 25.0
NULL_COLUMN_WARN_PCT = 50.0
NULL_COLUMNS_MANY_RATIO = 0.4
DUPLICATE_ROWS_WARN_PCT = 5.0
MIN_ROWS_FOR_DATETIME_HINT = 10
HIGH_CARD_UNIQ_MIN = 50
HIGH_CARD_RATIO = 0.95
NUMERIC_ALMOST_CONSTANT_MIN_ROWS = 10
NUMERIC_ALMOST_CONSTANT_DOMINANCE = 0.95
FINDING_MAX_VISIBLE = 6
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
