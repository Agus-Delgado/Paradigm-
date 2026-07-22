"""Features predecisionales para clustering (reusa contrato ml_v2, sin leakage)."""

from __future__ import annotations

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from paradigm.ml_v2.features import (
    FORBIDDEN_FEATURE_COLUMNS,
    PREDECISIONAL_CATEGORICAL,
    PREDECISIONAL_NUMERIC,
    assert_no_leakage,
)


def clustering_feature_columns() -> tuple[list[str], list[str]]:
    return list(PREDECISIONAL_CATEGORICAL), list(PREDECISIONAL_NUMERIC)


def build_clustering_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Solo columnas predecisionales; lanza si hay leakage en el feature set."""
    cat, num = clustering_feature_columns()
    missing = [c for c in cat + num if c not in df.columns]
    if missing:
        raise KeyError(f"Faltan features para clustering: {missing}")
    cols = cat + num
    assert_no_leakage(cols)
    out = df[cols].copy()
    assert_no_leakage(out.columns)
    overlap = set(out.columns) & set(FORBIDDEN_FEATURE_COLUMNS)
    if overlap:
        raise ValueError(f"Leakage en clustering frame: {sorted(overlap)}")
    return out


def make_preprocess() -> ColumnTransformer:
    cat, num = clustering_feature_columns()
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), num),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                cat,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )
