"""Paradigm — exploración y perfilado de datos (MVP)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from core.clinic_operational_insights import (
    build_clinic_operational_insights,
    clinic_operational_insights_available,
)
from core.clinic_operational_kpis import clinic_kpis_available, compute_clinic_kpis
from core.exploration import (
    MAX_FILTER_COLUMNS,
    build_filter_mask,
    chart_kinds_for_logical_type,
    count_active_specs,
    default_chart_kind,
    filterable_columns,
    pick_default_exploration_column,
)
from core.findings import Finding, build_findings
from core.ingestion import load_csv_path, load_uploaded_file
from core.profiling import (
    build_profile,
    count_logical_types,
    estimate_dataset_quality,
    profiles_to_dataframe,
)
from core.schema import infer_logical_types
from core.utils import PREVIEW_ROWS_MAX, PREVIEW_SAMPLE_RANDOM_STATE
from visualization.charts import (
    build_exploration_chart,
    chart_logical_type_distribution,
    chart_nulls_by_column,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_FLAT_CSV = REPO_ROOT / "data" / "sample" / "medical_clinic" / "medical_clinic_flat.csv"

SYNTHETIC_DATA_BANNER = (
    "Este dataset es completamente sintético y fue generado con fines demostrativos. "
    "No contiene información real de pacientes, profesionales ni de ninguna institución."
)

# Etiquetas en español para la UI (las claves internas siguen en inglés).
_LOGICAL_TYPE_LABEL_ES: dict[str, str] = {
    "numeric": "Numérico",
    "categorical": "Categórico",
    "boolean": "Booleano",
    "datetime": "Fecha / hora",
    "text": "Texto",
    "id": "Identificador",
}

_CHART_KIND_LABEL_ES: dict[str, str] = {
    "histograma": "Histograma",
    "boxplot": "Diagrama de caja",
    "barras": "Barras",
    "temporal": "Serie temporal",
    "ninguno": "Ninguno",
}


def _logical_type_label_es(logical_type: str) -> str:
    return _LOGICAL_TYPE_LABEL_ES.get(logical_type, logical_type)


def _chart_kind_label_es(kind: str) -> str:
    return _CHART_KIND_LABEL_ES.get(kind, kind)


def _render_operational_findings(findings: list[Finding]) -> None:
    for f in findings:
        st.info(f.message)


def _render_findings(findings: list[Finding]) -> None:
    if not findings:
        st.info(
            "Con las reglas actuales no se destacaron problemas graves. "
            "Podés revisar el detalle en el perfil por columna y en los gráficos."
        )
        return
    for f in findings:
        if f.severity == "warning":
            st.warning(f.message)
        else:
            st.info(f.message)


def _reset_exploration_session(uploaded_name: str, nrows: int, ncols: int) -> None:
    file_key = f"{uploaded_name}|{nrows}|{ncols}"
    if st.session_state.get("paradigm_data_key") == file_key:
        return
    st.session_state["paradigm_data_key"] = file_key
    for k in list(st.session_state.keys()):
        if k.startswith("pf_") or k.startswith("explore_") or k == "paradigm_filter_cols":
            del st.session_state[k]


def _sidebar_filter_specs(df: pd.DataFrame, logical: dict[str, str]) -> dict[str, dict]:
    """Construye specs de filtro desde widgets en sidebar."""
    specs: dict[str, dict] = {}
    eligible = filterable_columns(logical, list(df.columns))
    if not eligible:
        st.caption("No hay columnas categóricas, numéricas, booleanas o fecha para filtrar.")
        return specs

    chosen = st.multiselect(
        "Columnas para filtrar",
        options=eligible,
        help="Elegí hasta 6 columnas. Los tipos texto e identificador no se filtran en esta versión.",
        key="paradigm_filter_cols",
    )
    sel_cols = chosen[:MAX_FILTER_COLUMNS]
    if len(chosen) > MAX_FILTER_COLUMNS:
        st.caption(f"Solo se aplican las primeras {MAX_FILTER_COLUMNS} columnas seleccionadas.")

    for col in sel_cols:
        lt = logical.get(col, "text")
        key_cat = f"pf_cat_{col}"
        key_num = f"pf_num_{col}"
        key_bool = f"pf_bool_{col}"
        key_dt = f"pf_dt_{col}"

        if lt == "categorical":
            raw = df[col].dropna()
            if raw.empty:
                st.caption(f"{col}: sin valores para filtrar.")
                continue
            uniques = sorted(raw.astype(str).unique().tolist(), key=str)[:200]
            sel_vals = st.multiselect(
                f"{col}",
                options=uniques,
                default=[],
                key=key_cat,
                help="Vacío = sin filtro en esta columna.",
            )
            if sel_vals:
                specs[col] = {"kind": "categorical", "values": sel_vals}

        elif lt == "numeric":
            num = pd.to_numeric(df[col], errors="coerce")
            lo_f, hi_f = float(num.min()), float(num.max())
            if pd.isna(lo_f) or pd.isna(hi_f) or lo_f == hi_f:
                st.caption(f"{col}: rango numérico no disponible para filtrar.")
                continue
            lo, hi = st.slider(
                f"{col} (rango)",
                min_value=lo_f,
                max_value=hi_f,
                value=(lo_f, hi_f),
                key=key_num,
            )
            specs[col] = {"kind": "numeric", "lo": lo, "hi": hi}

        elif lt == "boolean":
            mode_label = st.selectbox(
                f"{col}",
                options=["Todos", "Verdadero", "Falso"],
                index=0,
                key=key_bool,
            )
            mode = {"Todos": "all", "Verdadero": "true", "Falso": "false"}[mode_label]
            if mode != "all":
                specs[col] = {"kind": "boolean", "mode": mode}

        elif lt == "datetime":
            dt = pd.to_datetime(df[col], errors="coerce").dropna()
            if dt.empty:
                st.caption(f"{col}: sin fechas válidas para filtrar.")
                continue
            dmin = dt.min().date()
            dmax = dt.max().date()
            dr = st.date_input(
                f"{col} (rango de fechas)",
                value=(dmin, dmax),
                min_value=dmin,
                max_value=dmax,
                key=key_dt,
            )
            if isinstance(dr, tuple) and len(dr) == 2:
                start_d, end_d = dr[0], dr[1]
                specs[col] = {"kind": "datetime", "start": start_d, "end": end_d}
            elif hasattr(dr, "year"):
                specs[col] = {"kind": "datetime", "start": dr, "end": dr}

    if st.button("Limpiar filtros", use_container_width=True):
        st.session_state["paradigm_filter_cols"] = []
        for k in list(st.session_state.keys()):
            if k.startswith("pf_"):
                del st.session_state[k]
        st.rerun()

    return specs


def main() -> None:
    st.set_page_config(page_title="Paradigm", layout="wide", page_icon="📊")
    st.title("Paradigm")
    st.caption(
        "Demo analítica de consultorio médico (datos sintéticos) y motor genérico de exploración para cualquier CSV/XLSX."
    )

    if "paradigm_stored_df" not in st.session_state:
        st.session_state["paradigm_stored_df"] = None
    if "paradigm_demo_clinic" not in st.session_state:
        st.session_state["paradigm_demo_clinic"] = False

    st.subheader("Cargar datos")
    st.caption(
        "Subí un CSV o Excel (primera hoja), o cargá el **dataset demo** del consultorio (tabla plana incluida en el repo)."
    )
    up_col, demo_col = st.columns([2, 1])
    with up_col:
        uploaded = st.file_uploader(
            "Archivo",
            type=["csv", "xlsx"],
            label_visibility="collapsed",
            help="Formatos: .csv (UTF-8 u otros encodings comunes) o .xlsx (primera hoja).",
        )
    with demo_col:
        st.write("")
        if st.button("Cargar dataset demo (consultorio médico)", use_container_width=True):
            demo_df, demo_err = load_csv_path(DEMO_FLAT_CSV)
            if demo_df is not None and demo_df.shape[1] > 0:
                st.session_state["paradigm_stored_df"] = demo_df
                st.session_state["paradigm_demo_clinic"] = True
                st.session_state["paradigm_active_label"] = "medical_clinic_flat.csv (dataset demo)"
                st.rerun()
            else:
                st.error(demo_err or "No se pudo cargar el dataset demo.")

    df: pd.DataFrame | None = None
    err: str | None = None
    active_name = "data"

    if uploaded is not None:
        df, err = load_uploaded_file(uploaded)
        if df is not None:
            st.session_state["paradigm_demo_clinic"] = False
            st.session_state["paradigm_stored_df"] = None
            active_name = uploaded.name or "archivo"
    elif st.session_state["paradigm_stored_df"] is not None:
        df = st.session_state["paradigm_stored_df"]
        active_name = str(st.session_state.get("paradigm_active_label", "dataset demo"))

    if df is None:
        if err:
            st.error(err)
        st.markdown(
            """
**Paradigm** ofrece una **primera lectura ejecutiva** sobre tablas cargadas desde archivo: infiere tipos de columnas,
resume nulos y duplicados, perfila cada campo y genera gráficos automáticos. El **dataset demo** simula operación de un consultorio ambulatorio con datos **100 % ficticios**.

**Qué podés hacer aquí**

- **Dataset demo:** botón arriba para cargar el CSV plano del consultorio (sin subir archivos).
- **Archivo propio:** subí cualquier CSV o Excel (primera hoja) como en un explorador genérico.
- KPIs globales, indicadores operativos opcionales (si el esquema coincide), filtros, vista previa y gráfico exploratorio.

**Otros ejemplos:** en `data/sample/` hay CSV adicionales para pruebas rápidas.
            """
        )
        return

    if df.shape[1] == 0:
        st.error("El dataset no tiene columnas para analizar.")
        return

    if st.session_state.get("paradigm_demo_clinic"):
        st.info(SYNTHETIC_DATA_BANNER)

    _reset_exploration_session(active_name, df.shape[0], df.shape[1])

    logical = infer_logical_types(df)
    if "explore_col_sb" not in st.session_state:
        st.session_state["explore_col_sb"] = pick_default_exploration_column(logical, list(df.columns))
    profile = build_profile(df, logical)
    detail_df = profiles_to_dataframe(profile)
    type_counts = count_logical_types(profile)
    quality_label, quality_hint = estimate_dataset_quality(profile)
    findings = build_findings(df, profile, logical)

    with st.sidebar:
        st.header("Exploración")
        st.caption(
            "Los filtros aplican a la vista previa y al gráfico exploratorio. "
            "El resumen ejecutivo y los hallazgos se calculan sobre el archivo completo."
        )
        filter_specs = _sidebar_filter_specs(df, logical)

    mask = build_filter_mask(df, logical, filter_specs)
    df_filtrado = df.loc[mask].copy()
    active_filters = count_active_specs(filter_specs) > 0

    st.divider()
    st.subheader("Resumen ejecutivo")
    st.caption(
        "Síntesis del archivo cargado completo: tamaño, nulos, duplicados, memoria, "
        "distribución de tipos inferidos y calidad estimada."
    )
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Filas", f"{profile.row_count:,}")
    m2.metric("Columnas", f"{profile.column_count:,}")
    m3.metric("% nulos (global)", f"{profile.null_pct:.2f}%")
    m4.metric("Filas duplicadas", f"{profile.duplicate_rows:,}")
    m5.metric("Memoria (aprox.)", f"{profile.memory_mb:.2f} MiB")

    q1, q2 = st.columns([1, 2])
    with q1:
        st.metric("Calidad estimada", quality_label)
    with q2:
        st.caption(
            f"{quality_hint} "
            "Es una **estimación heurística** (nulos, duplicados y forma general del perfil), no un índice estadístico."
        )

    fig_types = chart_logical_type_distribution(type_counts)
    st.plotly_chart(fig_types, use_container_width=True)
    st.caption("Cantidad de columnas por tipo inferido, sobre el **dataset completo** cargado.")

    if clinic_kpis_available(df):
        st.divider()
        st.subheader("Indicadores operativos (consultorio)")
        st.caption(
            "Métricas simples cuando el archivo incluye las columnas del dataset demo plano. "
            "En datasets sin esas columnas, este bloque no se muestra."
        )
        k = compute_clinic_kpis(df)
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Turnos (filas)", f"{k['n_turnos']:,}")
        r2.metric("% asistido", f"{k['pct_asistido']:.1f}%")
        r3.metric("% cancelado", f"{k['pct_cancelado']:.1f}%")
        r4.metric("% ausente", f"{k['pct_ausente']:.1f}%")
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("% reprogramado", f"{k['pct_reprogramado']:.1f}%")
        with s2:
            st.caption("Especialidad con mayor volumen")
            st.markdown(f"**{k['especialidad_mayor_volumen']}**")
        s3.metric("Ingreso neto total", f"{k['ingreso_neto_total']:,.2f}")
        with s4:
            st.caption("Medio de pago más frecuente")
            st.markdown(f"**{k['medio_pago_frecuente']}**")
        u1, _ = st.columns([1, 3])
        with u1:
            st.caption("Cobertura médica más frecuente")
            st.markdown(f"**{k['cobertura_medica_frecuente']}**")

    st.divider()
    if clinic_operational_insights_available(df):
        st.subheader("Hallazgos operativos del consultorio")
        st.caption(
            "Lecturas automáticas sobre columnas típicas de turnos y facturación; complementan el perfilado genérico."
        )
        op_list = build_clinic_operational_insights(df)
        if op_list:
            _render_operational_findings(op_list)
        else:
            st.info("No hay suficientes datos para generar hallazgos operativos.")

    st.subheader("Hallazgos de calidad de datos")
    st.caption(
        "Reglas fijas sobre el perfil del archivo completo; útiles para una primera pasada, sin modelos de ML."
    )
    _render_findings(findings)

    st.divider()
    st.subheader("Exploración (vista filtrada)")
    explore_caption = (
        "Vista previa y gráfico exploratorio usan el subconjunto definido en la barra lateral. "
        f"Filas en vista filtrada: **{len(df_filtrado):,}** de **{len(df):,}**."
    )
    if active_filters:
        explore_caption += (
            " Con filtros activos, el resumen ejecutivo, los indicadores operativos (si aplican) "
            "y los hallazgos de arriba siguen calculados sobre el archivo completo."
        )
    st.caption(explore_caption)

    if len(df_filtrado) == 0:
        st.warning("No hay filas que cumplan los filtros; probá ampliar criterios o usar **Limpiar filtros**.")
    else:
        cols_prev = st.columns([1, 1, 2])
        max_rows = len(df_filtrado)
        with cols_prev[0]:
            n_show = st.number_input(
                "Filas a mostrar",
                min_value=1,
                max_value=min(PREVIEW_ROWS_MAX, max_rows),
                value=min(50, max_rows),
                step=1,
                key="explore_preview_n",
            )
        with cols_prev[1]:
            preview_mode = st.radio(
                "Modo",
                options=["Primeras filas", "Muestra aleatoria"],
                horizontal=True,
                key="explore_preview_mode",
            )

        n = int(min(int(n_show), max_rows))
        if preview_mode == "Primeras filas":
            preview_df = df_filtrado.head(n)
        else:
            preview_df = df_filtrado.sample(n=n, random_state=PREVIEW_SAMPLE_RANDOM_STATE)

        cap_parts = [f"Mostrando {len(preview_df):,} fila(s)"]
        if n < max_rows:
            cap_parts.append(f"de {max_rows:,} en la vista filtrada")
        if active_filters:
            cap_parts.append("con filtros activos")
        st.caption(". ".join(cap_parts) + ".")
        st.dataframe(preview_df, use_container_width=True)

    st.subheader("Gráfico exploratorio")
    explore_col = st.selectbox(
        "Columna",
        options=list(df.columns),
        format_func=lambda c: f"{c} ({_logical_type_label_es(logical.get(c, 'text'))})",
        key="explore_col_sb",
    )
    lt_sel = logical.get(explore_col, "text")
    kinds = chart_kinds_for_logical_type(lt_sel)
    default_k = default_chart_kind(lt_sel)
    kind_idx = kinds.index(default_k) if default_k in kinds else 0
    chart_kind = st.selectbox(
        "Tipo de gráfico",
        options=kinds,
        index=kind_idx,
        key=f"explore_kind_{explore_col}",
        format_func=_chart_kind_label_es,
    )
    title = f"{explore_col} — {_chart_kind_label_es(chart_kind)} (vista filtrada)"
    series_explore = df_filtrado[explore_col] if len(df_filtrado) else df[explore_col].iloc[0:0]
    fig_explore = build_exploration_chart(series_explore, lt_sel, chart_kind, title)
    st.plotly_chart(fig_explore, use_container_width=True)

    st.divider()
    with st.expander("Perfil por columna", expanded=False):
        st.caption("Tipos inferidos, nulos, cardinalidad y detalle por campo.")
        st.dataframe(detail_df, use_container_width=True, hide_index=True)

    null_pcts = [float(x) for x in detail_df["% nulos"].tolist()]
    names = detail_df["columna"].tolist()
    fig_nulls = chart_nulls_by_column(names, null_pcts)

    st.divider()
    st.subheader("Gráficos (dataset completo)")
    st.caption(
        "Nulos por columna (%), respecto del archivo cargado completo. No dependen de los filtros de exploración."
    )
    st.plotly_chart(fig_nulls, use_container_width=True)


if __name__ == "__main__":
    main()
