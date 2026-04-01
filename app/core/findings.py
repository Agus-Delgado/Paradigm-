"""Hallazgos automáticos heurísticos (sin ML) a partir del perfil y del DataFrame."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.profiling import DatasetProfile
from core.utils import (
    DUPLICATE_ROWS_WARN_PCT,
    FINDING_MAX_VISIBLE,
    HIGH_CARD_RATIO,
    HIGH_CARD_UNIQ_MIN,
    MIN_ROWS_FOR_DATETIME_HINT,
    NULL_COLUMN_WARN_PCT,
    NUMERIC_ALMOST_CONSTANT_DOMINANCE,
    NUMERIC_ALMOST_CONSTANT_MIN_ROWS,
)

# Prioridad: menor número = más importante (se ordena antes)
PRIORITY_DUPLICATES = 10
PRIORITY_HIGH_NULLS = 20
PRIORITY_CONSTANT = 30
PRIORITY_ALMOST_CONSTANT = 35
PRIORITY_HIGH_CARD = 40
PRIORITY_ID = 50
PRIORITY_NO_DATETIME = 60


@dataclass(frozen=True)
class Finding:
    priority: int
    severity: str  # "warning" | "info"
    message: str


def build_findings(
    df: pd.DataFrame,
    profile: DatasetProfile,
    logical_types: dict[str, str],
) -> list[Finding]:
    """Genera hallazgos priorizados; el caller limita la visualización."""
    out: list[Finding] = []
    rows_n = profile.row_count
    if rows_n == 0:
        return []

    dup_pct = profile.duplicate_rows / rows_n * 100.0 if rows_n else 0.0
    if dup_pct > DUPLICATE_ROWS_WARN_PCT:
        out.append(
            Finding(
                PRIORITY_DUPLICATES,
                "warning",
                f"Filas duplicadas relevantes: {profile.duplicate_rows:,} "
                f"({dup_pct:.1f}% del total). Considerá revisar o deduplicar.",
            )
        )

    high_null_cols = [c.name for c in profile.columns if c.null_pct >= NULL_COLUMN_WARN_PCT]
    if high_null_cols:
        shown = high_null_cols[:3]
        extra = len(high_null_cols) - len(shown)
        suffix = f" y {extra} más" if extra > 0 else ""
        names = ", ".join(f"«{n}»" for n in shown)
        out.append(
            Finding(
                PRIORITY_HIGH_NULLS,
                "warning",
                f"Columnas con ≥{NULL_COLUMN_WARN_PCT:.0f}% de nulos: {names}{suffix}.",
            )
        )

    constant_cols = [
        c.name
        for c in profile.columns
        if c.unique_count == 1 and c.null_count < rows_n
    ]
    if constant_cols:
        shown = constant_cols[:4]
        extra = len(constant_cols) - len(shown)
        suffix = f" y {extra} más" if extra > 0 else ""
        names = ", ".join(f"«{n}»" for n in shown)
        out.append(
            Finding(
                PRIORITY_CONSTANT,
                "info",
                f"Columnas constantes (un solo valor distinto): {names}{suffix}.",
            )
        )

    almost = _almost_constant_numeric_columns(df, logical_types)
    if almost:
        shown = almost[:3]
        extra = len(almost) - len(shown)
        suffix = f" y {extra} más" if extra > 0 else ""
        names = ", ".join(f"«{n}»" for n in shown)
        out.append(
            Finding(
                PRIORITY_ALMOST_CONSTANT,
                "info",
                f"Columnas numéricas casi constantes (un valor domina ≥{NUMERIC_ALMOST_CONSTANT_DOMINANCE:.0%}): "
                f"{names}{suffix}.",
            )
        )

    high_card = [
        c.name
        for c in profile.columns
        if c.logical_type in ("categorical", "text")
        and c.unique_count >= HIGH_CARD_UNIQ_MIN
        and c.cardinality >= HIGH_CARD_RATIO
    ]
    if high_card:
        shown = high_card[:3]
        extra = len(high_card) - len(shown)
        suffix = f" y {extra} más" if extra > 0 else ""
        names = ", ".join(f"«{n}»" for n in shown)
        out.append(
            Finding(
                PRIORITY_HIGH_CARD,
                "info",
                f"Alta cardinalidad en texto/categoría (posible ID o texto libre): {names}{suffix}.",
            )
        )

    id_cols = [c.name for c in profile.columns if c.logical_type == "id"]
    if id_cols:
        shown = id_cols[:4]
        extra = len(id_cols) - len(shown)
        suffix = f" y {extra} más" if extra > 0 else ""
        names = ", ".join(f"«{n}»" for n in shown)
        out.append(
            Finding(
                PRIORITY_ID,
                "info",
                f"Posibles identificadores (únicos ≈ filas): {names}{suffix}.",
            )
        )

    if rows_n >= MIN_ROWS_FOR_DATETIME_HINT and not any(c.logical_type == "datetime" for c in profile.columns):
        out.append(
            Finding(
                PRIORITY_NO_DATETIME,
                "info",
                "No se detectó columna de fechas. Si esperabas serie temporal, revisá nombres y formatos.",
            )
        )

    out.sort(key=lambda f: (f.priority, f.severity))
    return out[:FINDING_MAX_VISIBLE]


def _almost_constant_numeric_columns(df: pd.DataFrame, logical_types: dict[str, str]) -> list[str]:
    found: list[str] = []
    for col in df.columns:
        if logical_types.get(col) != "numeric":
            continue
        num = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(num) < NUMERIC_ALMOST_CONSTANT_MIN_ROWS:
            continue
        if int(num.nunique()) != 2:
            continue
        top_freq = float(num.value_counts().iloc[0]) / len(num)
        if top_freq >= NUMERIC_ALMOST_CONSTANT_DOMINANCE:
            found.append(col)
    return found
