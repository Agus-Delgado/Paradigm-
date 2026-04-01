"""Paradigm — exploración y perfilado de datos (MVP)."""

from __future__ import annotations

import streamlit as st

from core.ingestion import load_uploaded_file
from core.profiling import build_profile, profiles_to_dataframe
from core.schema import infer_logical_types
from core.utils import PREVIEW_ROWS
from visualization.charts import (
    chart_categorical_top,
    chart_first_numeric_histogram,
    chart_nulls_by_column,
)


def _first_column_by_type(logical_types: dict[str, str], wanted: str) -> str | None:
    for col, lt in logical_types.items():
        if lt == wanted:
            return col
    return None


def _first_fallback_chart_column(logical_types: dict[str, str]) -> str | None:
    for prefer in ("categorical", "text", "boolean"):
        c = _first_column_by_type(logical_types, prefer)
        if c:
            return c
    return None


def main() -> None:
    st.set_page_config(page_title="Paradigm", layout="wide")
    st.title("Paradigm")
    st.caption("Exploración y perfilado automático de datasets (CSV / XLSX).")

    uploaded = st.file_uploader(
        "Subí un archivo",
        type=["csv", "xlsx"],
        help="Formatos: .csv (UTF-8 u otros encodings comunes) o .xlsx (primera hoja).",
    )

    if uploaded is None:
        st.info(
            "**Qué hace esta app:** carga tu tabla, infiere tipos de columnas, "
            "resume nulos y estadísticas básicas, y muestra un preview con gráficos automáticos. "
            "Ideal para una primera pasada sobre datos de cualquier dominio."
        )
        st.markdown("Podés probar con archivos de ejemplo en `data/sample/`.")
        return

    df, err = load_uploaded_file(uploaded)
    if err or df is None:
        st.error(err or "No se pudo cargar el archivo.")
        return

    if df.shape[1] == 0:
        st.error("El dataset no tiene columnas para analizar.")
        return

    logical = infer_logical_types(df)
    profile = build_profile(df, logical)
    detail_df = profiles_to_dataframe(profile)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Filas", f"{profile.row_count:,}")
    c2.metric("Columnas", f"{profile.column_count:,}")
    c3.metric("Nulos (total)", f"{profile.total_nulls:,}")
    c4.metric("% nulos (global)", f"{profile.null_pct:.2f}%")
    c5.metric("Filas duplicadas", f"{profile.duplicate_rows:,}")
    c6.metric("Memoria (aprox.)", f"{profile.memory_mb:.2f} MiB")

    st.divider()
    st.subheader("Vista previa")
    st.dataframe(df.head(PREVIEW_ROWS), use_container_width=True)

    st.divider()
    st.subheader("Perfil por columna")
    st.dataframe(detail_df, use_container_width=True, hide_index=True)

    null_pcts = [float(x) for x in detail_df["% nulos"].tolist()]
    names = detail_df["columna"].tolist()
    fig_nulls = chart_nulls_by_column(names, null_pcts)

    first_numeric = _first_column_by_type(logical, "numeric")
    first_cat = _first_column_by_type(logical, "categorical")
    if first_numeric:
        fig_second = chart_first_numeric_histogram(
            df[first_numeric],
            f"Distribución — {first_numeric} (numérica)",
        )
    elif first_cat:
        fig_second = chart_categorical_top(
            df[first_cat],
            f"Frecuencias — {first_cat} (categórica)",
        )
    else:
        fallback = _first_fallback_chart_column(logical)
        if fallback:
            fig_second = chart_categorical_top(df[fallback], f"Frecuencias — {fallback}")
        else:
            fig_second = chart_categorical_top(df[df.columns[0]], f"Frecuencias — {df.columns[0]}")

    st.divider()
    st.subheader("Gráficos")
    st.caption(
        "El gráfico de la derecha se elige automáticamente: primera columna numérica útil, "
        "si no hay, primera categórica; en otro caso, la primera columna disponible."
    )
    g1, g2 = st.columns(2)
    with g1:
        st.plotly_chart(fig_nulls, use_container_width=True)
    with g2:
        st.plotly_chart(fig_second, use_container_width=True)


if __name__ == "__main__":
    main()
