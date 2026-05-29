"""Insights heurísticos sobre el DataFrame (reutiliza perfil y tipos lógicos)."""

from __future__ import annotations

import pandas as pd

from core.profiling import DatasetProfile, count_logical_types, estimate_dataset_quality
from core.utils import NULL_COLUMN_WARN_PCT

IQR_MULTIPLIER = 1.5
MIN_ROWS_FOR_ZSCORE = 30
ZSCORE_THRESHOLD = 3.0
MIN_GROUP_ROWS = 10
MAX_OUTLIER_COLUMNS = 3
MAX_TOP_CATEGORY_COLS = 3


def build_dataset_overview(
    df: pd.DataFrame,
    profile: DatasetProfile,
    logical_types: dict[str, str],
) -> list[str]:
    """Bullets de panorama: tamaño, tipos, calidad, nulos destacados."""
    bullets: list[str] = []
    bullets.append(
        f"El dataset tiene {profile.row_count:,} filas y {profile.column_count} columnas "
        f"({profile.null_pct:.2f}% de celdas nulas a nivel global)."
    )

    type_counts = count_logical_types(profile)
    if type_counts:
        parts = [f"{k}: {v}" for k, v in type_counts.items()]
        bullets.append("Tipos inferidos por columna: " + "; ".join(parts) + ".")

    quality_label, quality_hint = estimate_dataset_quality(profile)
    bullets.append(f"Calidad estimada: {quality_label} ({quality_hint})")

    high_null = [c.name for c in profile.columns if c.null_pct >= NULL_COLUMN_WARN_PCT]
    if high_null:
        shown = high_null[:4]
        extra = len(high_null) - len(shown)
        suffix = f" y {extra} más" if extra > 0 else ""
        bullets.append(
            f"Columnas con ≥{NULL_COLUMN_WARN_PCT:.0f}% de nulos: "
            + ", ".join(f"«{n}»" for n in shown)
            + suffix
            + "."
        )

    numeric_cols = [c for c in df.columns if logical_types.get(c) == "numeric"]
    cat_cols = [c for c in df.columns if logical_types.get(c) == "categorical"]
    if numeric_cols:
        bullets.append(f"Columnas numéricas detectadas ({len(numeric_cols)}): " + ", ".join(numeric_cols[:6]) + ".")
    if cat_cols:
        bullets.append(f"Columnas categóricas detectadas ({len(cat_cols)}): " + ", ".join(cat_cols[:6]) + ".")

    return bullets


def top_categories_insights(df: pd.DataFrame, logical_types: dict[str, str], limit_cols: int = 3) -> list[str]:
    """Top categoría por columna categórica con cardinalidad moderada."""
    out: list[str] = []
    for col in df.columns:
        if logical_types.get(col) != "categorical":
            continue
        if len(out) >= limit_cols:
            break
        raw = df[col].dropna()
        if raw.empty:
            continue
        nunique = int(raw.nunique())
        if nunique < 2 or nunique > 50:
            continue
        vc = raw.astype(str).value_counts()
        top_val = vc.index[0]
        share = float(vc.iloc[0]) / float(len(raw)) * 100.0
        out.append(f"«{col}»: valor más frecuente «{top_val}» ({share:.1f}% de no nulos).")
    return out


def iqr_outlier_summary(df: pd.DataFrame, col: str) -> tuple[int, float] | None:
    """Cuenta de outliers por IQR; retorna (count, pct_of_non_null) o None."""
    num = pd.to_numeric(df[col], errors="coerce").dropna()
    if len(num) < 4:
        return None
    q1 = float(num.quantile(0.25))
    q3 = float(num.quantile(0.75))
    iqr = q3 - q1
    if iqr == 0:
        return None
    lo = q1 - IQR_MULTIPLIER * iqr
    hi = q3 + IQR_MULTIPLIER * iqr
    mask = (num < lo) | (num > hi)
    count = int(mask.sum())
    if count == 0:
        return None
    pct = count / len(num) * 100.0
    return count, pct


def detect_numeric_outliers(
    df: pd.DataFrame,
    logical_types: dict[str, str],
) -> tuple[list[str], list[str]]:
    """Hallazgos de outliers IQR; data_used = nombres de columnas reportadas."""
    findings: list[str] = []
    data_used: list[str] = []
    ranked: list[tuple[str, int, float]] = []

    for col in df.columns:
        if logical_types.get(col) != "numeric":
            continue
        summary = iqr_outlier_summary(df, col)
        if summary is None:
            continue
        count, pct = summary
        ranked.append((col, count, pct))

    ranked.sort(key=lambda x: (-x[1], -x[2]))
    for col, count, pct in ranked[:MAX_OUTLIER_COLUMNS]:
        data_used.append(col)
        findings.append(
            f"«{col}»: {count:,} valores fuera de [Q1−1.5·IQR, Q3+1.5·IQR] "
            f"({pct:.1f}% de valores no nulos)."
        )

    if not findings:
        findings.append(
            "No se detectaron outliers claros por IQR en las columnas numéricas analizadas."
        )

    return findings, data_used


def zscore_outlier_note(df: pd.DataFrame, col: str) -> str | None:
    """Nota opcional con z-score para columnas con suficientes filas."""
    num = pd.to_numeric(df[col], errors="coerce").dropna()
    if len(num) < MIN_ROWS_FOR_ZSCORE:
        return None
    std = float(num.std())
    if std == 0:
        return None
    z = ((num - num.mean()) / std).abs()
    n_extreme = int((z > ZSCORE_THRESHOLD).sum())
    if n_extreme == 0:
        return None
    pct = n_extreme / len(num) * 100.0
    return (
        f"«{col}» (z-score): {n_extreme} valores con |z|>{ZSCORE_THRESHOLD:.0f} "
        f"({pct:.1f}% de no nulos)."
    )


def missing_columns_report(profile: DatasetProfile) -> tuple[list[str], list[str]]:
    """Columnas con nulos, ordenadas por % descendente."""
    with_nulls = [(c.name, c.null_pct, c.null_count) for c in profile.columns if c.null_count > 0]
    with_nulls.sort(key=lambda x: (-x[1], x[0]))
    if not with_nulls:
        return ["No hay valores nulos en ninguna columna."], []

    findings: list[str] = []
    data_used: list[str] = []
    for name, pct, count in with_nulls[:8]:
        data_used.append(name)
        findings.append(f"«{name}»: {count:,} nulos ({pct:.2f}% de filas).")
    if len(with_nulls) > 8:
        findings.append(f"… y {len(with_nulls) - 8} columnas más con al menos un nulo.")
    return findings, data_used


def search_columns_by_tokens(
    df: pd.DataFrame,
    profile: DatasetProfile,
    tokens: list[str],
) -> tuple[list[str], list[str]]:
    """Busca columnas cuyo nombre contiene algún token de la pregunta."""
    if not tokens:
        return [], []

    matches: list[str] = []
    for col in df.columns:
        col_norm = col.lower().replace("_", " ")
        if any(t in col_norm or t in col.lower() for t in tokens):
            matches.append(col)

    if not matches:
        return [], []

    findings: list[str] = []
    col_by_name = {c.name: c for c in profile.columns}
    for col in matches[:10]:
        cp = col_by_name.get(col)
        if cp:
            findings.append(
                f"«{col}» ({cp.logical_type}): {cp.null_count:,} nulos, "
                f"{cp.unique_count} valores únicos."
            )
        else:
            findings.append(f"Columna coincidente: «{col}».")
    return findings, matches[:10]


def compare_categorical_numeric(
    df: pd.DataFrame,
    cat_col: str,
    num_col: str,
    min_group_rows: int = MIN_GROUP_ROWS,
) -> str | None:
    """Compara media numérica entre grupos categóricos (top 2 por volumen)."""
    sub = df[[cat_col, num_col]].copy()
    sub[num_col] = pd.to_numeric(sub[num_col], errors="coerce")
    sub = sub.dropna()
    if sub.empty:
        return None

    grp = sub.groupby(sub[cat_col].astype(str), dropna=False)[num_col]
    stats = grp.agg(["mean", "count"]).sort_values("count", ascending=False)
    stats = stats[stats["count"] >= min_group_rows]
    if len(stats) < 2:
        return None

    top2 = stats.head(2)
    low_row = top2["mean"].idxmin()
    high_row = top2["mean"].idxmax()
    low_mean = float(top2.loc[low_row, "mean"])
    high_mean = float(top2.loc[high_row, "mean"])
    return (
        f"Comparación «{cat_col}» vs «{num_col}» (grupos con ≥{min_group_rows} filas): "
        f"menor media en «{low_row}» ({low_mean:,.2f}), mayor en «{high_row}» ({high_mean:,.2f})."
    )


def compare_clinic_estado(df: pd.DataFrame) -> str | None:
    """Comparación simple de tasas de estado_turno si existe."""
    if "estado_turno" not in df.columns or len(df) == 0:
        return None
    est = df["estado_turno"].astype(str).str.strip().str.lower()
    vc = est.value_counts()
    if len(vc) < 2:
        return None
    parts = [f"«{idx}»: {100.0 * v / len(df):.1f}%" for idx, v in vc.head(4).items()]
    return "Distribución de estados de turno: " + "; ".join(parts) + "."


def compare_clinic_especialidad_ingreso(df: pd.DataFrame) -> str | None:
    """Especialidad con menor ingreso neto medio (underperformance proxy)."""
    if "especialidad" not in df.columns or "ingreso_neto" not in df.columns:
        return None
    sub = df[["especialidad", "ingreso_neto"]].copy()
    sub["ingreso_neto"] = pd.to_numeric(sub["ingreso_neto"], errors="coerce")
    sub = sub.dropna()
    if sub.empty:
        return None
    grp = sub.groupby(sub["especialidad"].astype(str))["ingreso_neto"]
    means = grp.mean()
    counts = grp.count()
    valid = means[counts >= MIN_GROUP_ROWS]
    if len(valid) < 2:
        return None
    low_esp = valid.idxmin()
    high_esp = valid.idxmax()
    return (
        f"Ingreso neto medio por especialidad: menor en «{low_esp}» ({valid[low_esp]:,.2f}), "
        f"mayor en «{high_esp}» ({valid[high_esp]:,.2f})."
    )


def pick_compare_pair(
    df: pd.DataFrame,
    logical_types: dict[str, str],
) -> tuple[str, str] | None:
    """Elige par categórico + numérico para comparación genérica."""
    cats = [c for c in df.columns if logical_types.get(c) == "categorical"]
    nums = [c for c in df.columns if logical_types.get(c) == "numeric"]
    if not cats or not nums:
        return None
    best_cat = None
    best_score = -1
    for col in cats:
        n = int(df[col].dropna().nunique())
        if 2 <= n <= 20:
            score = len(df) - abs(n - 5)
            if score > best_score:
                best_score = score
                best_cat = col
    if best_cat is None:
        best_cat = cats[0]
    return best_cat, nums[0]


def suggest_filters(
    df: pd.DataFrame,
    logical_types: dict[str, str],
    query_tokens: list[str],
) -> tuple[list[str], list[str]]:
    """Sugerencias de filtro sin aplicar sidebar."""
    from core.exploration import filterable_columns

    eligible = filterable_columns(logical_types, list(df.columns))
    findings: list[str] = []
    data_used: list[str] = []

    mentioned = [c for c in eligible if any(t in c.lower() for t in query_tokens)]
    target_cols = mentioned[:3] if mentioned else eligible[:3]

    for col in target_cols:
        data_used.append(col)
        lt = logical_types.get(col, "text")
        if lt == "categorical":
            vals = df[col].dropna().astype(str).value_counts().head(5)
            top = ", ".join(f"«{k}»" for k in vals.index[:3])
            findings.append(f"Filtro sugerido en «{col}» (categórica): valores frecuentes {top}.")
        elif lt == "numeric":
            num = pd.to_numeric(df[col], errors="coerce").dropna()
            if not num.empty:
                findings.append(
                    f"Filtro sugerido en «{col}» (numérica): rango observado "
                    f"{float(num.min()):g} – {float(num.max()):g}."
                )
        elif lt == "boolean":
            findings.append(f"Filtro sugerido en «{col}» (booleana): Verdadero / Falso.")
        elif lt == "datetime":
            dt = pd.to_datetime(df[col], errors="coerce").dropna()
            if not dt.empty:
                findings.append(
                    f"Filtro sugerido en «{col}» (fecha): "
                    f"{dt.min().date()} a {dt.max().date()}."
                )

    if not findings:
        findings.append(
            "No hay columnas filtrables detectadas. Usá tipos categórico, numérico, booleano o fecha."
        )

    return findings, data_used
