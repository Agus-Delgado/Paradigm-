"""Data Explorer: filtros dinámicos, preview y puente al Análisis Guiado."""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import streamlit as st

from app.conversational.legacy_bridge import exploration_build_filter_mask, exploration_filterable_columns
from app.conversational.types import DatasetContext
MAX_FILTER_COLUMNS = 6
PREVIEW_ROWS_DEFAULT = 50


def _filter_cols_key(dataset_key: str) -> str:
    return f"explorer_filter_cols_{dataset_key}"


def _stats_col_key(dataset_key: str) -> str:
    return f"explorer_stats_col_{dataset_key}"


_LOGICAL_LABEL_ES: dict[str, str] = {
    "numeric": "Numérico",
    "categorical": "Categórico",
    "boolean": "Booleano",
    "datetime": "Fecha",
    "text": "Texto",
    "id": "ID",
}


def _badge_class(logical_type: str) -> str:
    return f"explorer-col-badge explorer-col-badge--{logical_type}"


def _render_column_list(ctx: DatasetContext) -> None:
    st.markdown("**Columnas**")
    for col in ctx.df.columns:
        lt = ctx.logical_types.get(col, "text")
        label = _LOGICAL_LABEL_ES.get(lt, lt)
        st.markdown(
            f'<div class="explorer-col-row">'
            f'<span class="explorer-col-name">{col}</span>'
            f'<span class="{_badge_class(lt)}">{label}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )


def _build_filter_specs(df: pd.DataFrame, logical: dict[str, str], dataset_key: str) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    eligible = exploration_filterable_columns(logical, list(df.columns))
    if not eligible:
        st.caption("No hay columnas filtrables en este dataset.")
        return specs

    chosen = st.multiselect(
        "Columnas para filtrar",
        options=eligible,
        key=_filter_cols_key(dataset_key),
        help=f"Hasta {MAX_FILTER_COLUMNS} columnas.",
    )
    sel_cols = chosen[:MAX_FILTER_COLUMNS]
    if len(chosen) > MAX_FILTER_COLUMNS:
        st.caption(f"Solo se aplican las primeras {MAX_FILTER_COLUMNS} columnas.")

    for col in sel_cols:
        lt = logical.get(col, "text")
        if lt == "categorical":
            raw = df[col].dropna()
            if raw.empty:
                continue
            uniques = sorted(raw.astype(str).unique().tolist(), key=str)[:200]
            sel_vals = st.multiselect(
                col,
                options=uniques,
                default=[],
                key=f"explorer_pf_cat_{dataset_key}_{col}",
            )
            if sel_vals:
                specs[col] = {"kind": "categorical", "values": sel_vals}

        elif lt == "numeric":
            num = pd.to_numeric(df[col], errors="coerce")
            lo_f, hi_f = float(num.min()), float(num.max())
            if pd.isna(lo_f) or pd.isna(hi_f) or lo_f == hi_f:
                st.caption(f"{col}: rango no disponible.")
                continue
            lo, hi = st.slider(
                f"{col}",
                min_value=lo_f,
                max_value=hi_f,
                value=(lo_f, hi_f),
                key=f"explorer_pf_num_{dataset_key}_{col}",
            )
            specs[col] = {"kind": "numeric", "lo": lo, "hi": hi}

        elif lt == "boolean":
            mode_label = st.selectbox(
                col,
                options=["Todos", "Verdadero", "Falso"],
                index=0,
                key=f"explorer_pf_bool_{dataset_key}_{col}",
            )
            mode = {"Todos": "all", "Verdadero": "true", "Falso": "false"}[mode_label]
            if mode != "all":
                specs[col] = {"kind": "boolean", "mode": mode}

        elif lt == "datetime":
            dt = pd.to_datetime(df[col], errors="coerce").dropna()
            if dt.empty:
                continue
            dmin = dt.min().date()
            dmax = dt.max().date()
            dr = st.date_input(
                f"{col}",
                value=(dmin, dmax),
                min_value=dmin,
                max_value=dmax,
                key=f"explorer_pf_dt_{dataset_key}_{col}",
            )
            if isinstance(dr, tuple) and len(dr) == 2:
                specs[col] = {"kind": "datetime", "start": dr[0], "end": dr[1]}
            elif hasattr(dr, "year"):
                specs[col] = {"kind": "datetime", "start": dr, "end": dr}

    return specs


def _render_quick_stats(df: pd.DataFrame, col: str, logical_type: str) -> None:
    st.markdown(f"**Estadísticas: `{col}`**")
    series = df[col]
    if logical_type == "numeric":
        num = pd.to_numeric(series, errors="coerce")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Min", f"{num.min():,.2f}" if num.notna().any() else "—")
        c2.metric("Max", f"{num.max():,.2f}" if num.notna().any() else "—")
        c3.metric("Media", f"{num.mean():,.2f}" if num.notna().any() else "—")
        c4.metric("Nulos", f"{int(num.isna().sum()):,}")
    elif logical_type in ("categorical", "boolean", "text"):
        vc = series.astype(str).value_counts().head(3)
        st.caption("Top valores")
        for val, cnt in vc.items():
            st.markdown(f"- **{val}**: {cnt:,}")
        st.caption(f"Únicos: {series.nunique():,} · Nulos: {series.isna().sum():,}")
    elif logical_type == "datetime":
        dt = pd.to_datetime(series, errors="coerce")
        valid = dt.dropna()
        if not valid.empty:
            c1, c2 = st.columns(2)
            c1.metric("Desde", str(valid.min().date()))
            c2.metric("Hasta", str(valid.max().date()))
        st.caption(f"Nulos: {dt.isna().sum():,}")
    else:
        st.caption(f"Filas: {len(series):,} · Únicos: {series.nunique():,}")


def render_data_explorer(
    ctx: DatasetContext,
    *,
    on_explore_ia: Callable[[DatasetContext], None] | None = None,
) -> None:
    dk = ctx.dataset_key
    df = ctx.df
    logical = ctx.logical_types

    st.markdown(
        '<div class="explorer-nav-card">'
        '<span class="explorer-nav-label">Data Explorer</span>'
        f'<span class="explorer-nav-meta">{len(df):,} filas · {len(df.columns)} columnas</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    left, right = st.columns([1, 2.5], gap="large")

    with left:
        st.markdown('<div class="explorer-sidebar-card">', unsafe_allow_html=True)
        _render_column_list(ctx)
        st.divider()
        st.markdown("**Filtros**")
        specs = _build_filter_specs(df, logical, dk)
        st.markdown("</div>", unsafe_allow_html=True)

    mask = exploration_build_filter_mask(df, logical, specs)
    df_filtered = df.loc[mask].copy()
    pct = (len(df_filtered) / len(df)) * 100 if len(df) else 0.0

    with right:
        m1, m2, m3 = st.columns(3)
        m1.metric("Filas filtradas", f"{len(df_filtered):,}")
        m2.metric("Total dataset", f"{len(df):,}")
        m3.metric("% retenido", f"{pct:.1f}%")

        stats_col = st.selectbox(
            "Columna para estadísticas rápidas",
            options=list(df.columns),
            key=_stats_col_key(dk),
        )
        if stats_col:
            _render_quick_stats(df_filtered, stats_col, logical.get(stats_col, "text"))

        st.divider()
        n_show = st.number_input(
            "Filas en vista previa",
            min_value=1,
            max_value=min(500, max(1, len(df_filtered))),
            value=min(PREVIEW_ROWS_DEFAULT, max(1, len(df_filtered))),
            key=f"explorer_preview_n_{dk}",
        )
        preview = df_filtered.head(int(n_show))
        st.dataframe(preview, use_container_width=True, hide_index=True)

        if on_explore_ia is not None:
            st.markdown('<div class="explorer-ia-cta">', unsafe_allow_html=True)
            if st.button(
                "Explorar con IA",
                type="primary",
                use_container_width=True,
                key=f"explorer_ia_{dk}",
                help="Aplica los filtros actuales y abre el Análisis Guiado sobre este subset.",
            ):
                on_explore_ia(ctx, df_filtered)
            st.markdown("</div>", unsafe_allow_html=True)

        if len(df_filtered) == 0:
            st.warning(
                "Ninguna fila coincide con los filtros actuales. "
                "Ampliá rangos o quitá criterios para continuar explorando."
            )
        elif len(df_filtered) == len(df):
            st.caption("Vista completa del dataset — sin filtros restrictivos activos.")


def make_explore_ia_handler(
    *,
    set_active_tab: Callable[[str], None],
    skip_key_fn: Callable[[str], str],
    answers_key_fn: Callable[[str, str], str],
    pending_run_key_fn: Callable[[str], str],
) -> Callable[[DatasetContext, pd.DataFrame], None]:
    """Factory para el callback «Explorar con IA»."""

    def handler(ctx: DatasetContext, df_filtered: pd.DataFrame) -> None:
        from app.data import prepare_dataset_context

        label = f"Subset explorador ({len(df_filtered):,} filas)"
        new_ctx = prepare_dataset_context(
            df_filtered,
            source="explorer",
            source_label=label,
        )
        st.session_state["analyst_v2_ctx"] = new_ctx
        dk = new_ctx.dataset_key
        st.session_state[skip_key_fn(dk)] = True
        st.session_state[answers_key_fn("wizard", dk)] = {
            "objective": f"Exploración del subset filtrado ({len(df_filtered):,} filas)",
        }
        st.session_state[pending_run_key_fn(dk)] = True
        set_active_tab("Análisis Guiado")
        st.rerun()

    return handler
