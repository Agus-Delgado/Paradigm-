"""UI inmersiva del SQL Explorer."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from app.conversational.nl_to_sql import generate_sql
from app.conversational.plots import build_sql_result_chart
from app.conversational.sql_engine import TABLE_NAME, ensure_engine_ready, execute_sql_on_dataframe
from app.conversational.types import DatasetContext
from app.config import COLOR_PRIMARY_SOFT, COLOR_WARNING
from app.export_report import build_sql_report_md
from app.ui import COLOR_MUTED


def _history_key(dataset_key: str) -> str:
    return f"sql_history_{dataset_key}"


def _editor_key(dataset_key: str) -> str:
    return f"sql_editor_{dataset_key}"


def _result_key(dataset_key: str) -> str:
    return f"sql_last_result_{dataset_key}"


def _append_history(dataset_key: str, entry: dict) -> None:
    key = _history_key(dataset_key)
    hist = st.session_state.setdefault(key, [])
    hist.insert(0, entry)
    st.session_state[key] = hist[:30]


def render_sql_explorer(ctx: DatasetContext) -> None:
    dk = ctx.dataset_key
    ensure_engine_ready(dk, ctx.df)

    st.markdown(
        f'<div class="explorer-nav-card">'
        f'<span class="explorer-nav-label">SQL Explorer</span>'
        f'<span class="explorer-nav-meta">Tabla: <code>{TABLE_NAME}</code> · '
        f"{len(ctx.df):,} filas · {len(ctx.df.columns)} columnas</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.caption(
        "Explorá el dataset con SQL de solo lectura (SELECT / WITH). "
        "Cada ejecución usa una copia SQLite en memoria — segura y aislada."
    )

    # ── NL → SQL ──────────────────────────────────────────────
    with st.expander("Lenguaje natural → SQL", expanded=True):
        nl_col1, nl_col2 = st.columns([4, 1])
        with nl_col1:
            nl_prompt = st.text_input(
                "Describí qué querés ver",
                placeholder='Ej.: "muéstrame los clientes con mayor desvío" o "comparar especialidad con ingreso"',
                key=f"sql_nl_prompt_{dk}",
                label_visibility="collapsed",
            )
        with nl_col2:
            gen_clicked = st.button("Generar SQL", type="primary", use_container_width=True, key=f"sql_gen_{dk}")

        if gen_clicked and nl_prompt.strip():
            sql_text, explanation = generate_sql(
                nl_prompt.strip(),
                ctx.df,
                ctx.logical_types,
                ctx.domain,
            )
            st.session_state[_editor_key(dk)] = sql_text
            st.session_state[f"sql_nl_explanation_{dk}"] = explanation
            st.session_state[f"sql_nl_last_{dk}"] = nl_prompt.strip()
            st.rerun()

        explanation = st.session_state.get(f"sql_nl_explanation_{dk}")
        if explanation:
            st.info(
                f"**Sugerencia generada:** {explanation} "
                "Revisá y editá el SQL antes de ejecutar."
            )

    # ── Editor ────────────────────────────────────────────────
    editor_key = _editor_key(dk)
    if editor_key not in st.session_state:
        st.session_state[editor_key] = f"SELECT * FROM {TABLE_NAME} LIMIT 20"

    st.markdown('<div class="sql-editor-wrap">', unsafe_allow_html=True)
    sql_input = st.text_area(
        "Editor SQL",
        height=220,
        key=editor_key,
        label_visibility="collapsed",
        help="Sintaxis SQLite. Tabla principal: data",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    btn_col1, btn_col2, btn_col3 = st.columns([2, 1, 1])
    with btn_col1:
        run_clicked = st.button("Ejecutar", type="primary", use_container_width=True, key=f"sql_run_{dk}")
    with btn_col2:
        if st.button("Limpiar", use_container_width=True, key=f"sql_clear_{dk}"):
            st.session_state[editor_key] = f"SELECT * FROM {TABLE_NAME} LIMIT 20"
            st.session_state.pop(_result_key(dk), None)
            st.session_state.pop(f"sql_show_chart_{dk}", None)
            st.rerun()
    with btn_col3:
        if st.button("Ejemplo COUNT", use_container_width=True, key=f"sql_ex_count_{dk}"):
            st.session_state[editor_key] = f"SELECT COUNT(*) AS filas FROM {TABLE_NAME}"
            st.rerun()

    # ── Ejecución ─────────────────────────────────────────────
    if run_clicked and sql_input.strip():
        with st.spinner("Ejecutando consulta…"):
            result_df, err = execute_sql_on_dataframe(ctx.df, sql_input.strip())
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if err:
            st.error(err)
            _append_history(
                dk,
                {
                    "sql": sql_input.strip(),
                    "nl_prompt": st.session_state.get(f"sql_nl_last_{dk}"),
                    "rows": 0,
                    "ok": False,
                    "error": err,
                    "ts": ts,
                },
            )
        else:
            st.session_state[_result_key(dk)] = result_df
            st.session_state[f"sql_show_chart_{dk}"] = True
            _append_history(
                dk,
                {
                    "sql": sql_input.strip(),
                    "nl_prompt": st.session_state.get(f"sql_nl_last_{dk}"),
                    "rows": len(result_df) if result_df is not None else 0,
                    "ok": True,
                    "error": None,
                    "ts": ts,
                },
            )

    result_df: pd.DataFrame | None = st.session_state.get(_result_key(dk))
    last_sql = st.session_state.get(editor_key, "")
    if result_df is not None:
        st.markdown(
            f'<p class="sql-results-header">Resultados '
            f'<span style="color:{COLOR_MUTED};font-weight:400;">'
            f"({len(result_df):,} filas × {len(result_df.columns)} columnas)</span></p>",
            unsafe_allow_html=True,
        )
        report_md = build_sql_report_md(
            last_sql,
            result_df,
            ctx,
            nl_prompt=st.session_state.get(f"sql_nl_last_{dk}"),
        )
        st.download_button(
            "Exportar reporte",
            data=report_md,
            file_name=f"paradigm_sql_{dk[:8]}.md",
            mime="text/markdown",
            help="Informe Markdown con la consulta y una muestra de resultados.",
            key=f"sql_export_{dk}",
        )
        st.dataframe(result_df, use_container_width=True, hide_index=True)

        if result_df.empty:
            st.caption("La consulta no devolvió filas. Probá ampliar criterios o revisar filtros.")
        else:
            show_chart = st.session_state.get(f"sql_show_chart_{dk}", False)
            gen_chart = st.button("Regenerar gráfico", type="secondary", key=f"sql_chart_{dk}")
            if show_chart or gen_chart:
                fig = build_sql_result_chart(result_df)
                st.plotly_chart(fig, use_container_width=True)
                st.session_state[f"sql_show_chart_{dk}"] = True
    elif run_clicked:
        pass
    else:
        st.markdown(
            f'<div class="insight-card" style="text-align:center;color:{COLOR_MUTED};">'
            "Escribí o generá una consulta y presioná <strong>Ejecutar</strong> "
            f"para ver resultados sobre la tabla <code>{TABLE_NAME}</code>."
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Historial ─────────────────────────────────────────────
    history = st.session_state.get(_history_key(dk), [])
    if history:
        with st.expander(f"Historial de consultas ({len(history)})", expanded=False):
            for i, item in enumerate(history):
                status = "OK" if item.get("ok") else "Error"
                color = COLOR_PRIMARY_SOFT if item.get("ok") else COLOR_WARNING
                label = item["sql"][:80] + ("…" if len(item["sql"]) > 80 else "")
                cols = st.columns([5, 1])
                with cols[0]:
                    st.markdown(
                        f'<span style="color:{color};font-size:0.75rem;font-weight:600;">{status}</span> '
                        f'<code style="font-size:0.8rem;">{label}</code>',
                        unsafe_allow_html=True,
                    )
                    if item.get("nl_prompt"):
                        st.caption(f"NL: {item['nl_prompt']}")
                with cols[1]:
                    if st.button("Reusar", key=f"sql_reuse_{dk}_{i}"):
                        st.session_state[_editor_key(dk)] = item["sql"]
                        st.rerun()
