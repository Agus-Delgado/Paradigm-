"""UI inmersiva del SQL Explorer."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from app.config.llm_config import is_llm_available
from app.conversational.ai_analyst_ui import llm_spinner_message, render_ai_workspace_chrome
from app.conversational.nl_to_sql import _generate_sql_heuristic, generate_sql_llm_enhanced
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

    render_ai_workspace_chrome(ctx, tab_suffix="sql_top")

    st.caption(
        "Explorá el dataset con SQL de solo lectura (SELECT / WITH). "
        "NL→SQL híbrido: AI Analyst + fallback heurístico."
    )

    # ── NL → SQL ──────────────────────────────────────────────
    with st.expander("Lenguaje natural → SQL (AI Analyst)", expanded=True):
        nl_col1, nl_col2 = st.columns([4, 1])
        with nl_col1:
            nl_prompt = st.text_input(
                "Describí qué querés ver",
                placeholder='Ej.: "tasa de no-show por especialidad" o "comparar canal con ingreso"',
                key=f"sql_nl_prompt_{dk}",
                label_visibility="collapsed",
            )
        with nl_col2:
            gen_clicked = st.button("Generar SQL", type="primary", use_container_width=True, key=f"sql_gen_{dk}")

        if gen_clicked and nl_prompt.strip():
            spinner = llm_spinner_message()
            with st.spinner(spinner):
                sql_result = generate_sql_llm_enhanced(
                    nl_prompt.strip(),
                    ctx.df,
                    ctx.logical_types,
                    ctx.domain,
                )
                heuristic_sql, heuristic_exp = _generate_sql_heuristic(
                    nl_prompt.strip(),
                    ctx.df,
                    ctx.logical_types,
                    ctx.domain,
                )
            st.session_state[_editor_key(dk)] = sql_result.sql
            st.session_state[f"sql_nl_explanation_{dk}"] = sql_result.explanation
            st.session_state[f"sql_nl_engine_{dk}"] = sql_result.engine
            st.session_state[f"sql_nl_confidence_{dk}"] = sql_result.confidence
            st.session_state[f"sql_nl_sources_{dk}"] = sql_result.sources
            st.session_state[f"sql_nl_heuristic_{dk}"] = heuristic_sql
            st.session_state[f"sql_nl_heuristic_exp_{dk}"] = heuristic_exp
            st.session_state[f"sql_nl_last_{dk}"] = nl_prompt.strip()
            st.session_state[f"sql_nl_used_llm_{dk}"] = sql_result.used_llm
            st.rerun()

        engine = st.session_state.get(f"sql_nl_engine_{dk}")
        explanation = st.session_state.get(f"sql_nl_explanation_{dk}")
        used_llm = st.session_state.get(f"sql_nl_used_llm_{dk}")
        if explanation or engine:
            badge = "LLM + RAG" if used_llm else "Heurístico"
            badge_color = COLOR_PRIMARY_SOFT if used_llm else COLOR_WARNING
            st.markdown(
                f'<div class="insight-card">'
                f'<span style="color:{badge_color};font-weight:600;font-size:0.8rem;">{badge}</span> '
                f"<strong>Explicación:</strong> {explanation or '—'}"
                f"</div>",
                unsafe_allow_html=True,
            )
            confidence = st.session_state.get(f"sql_nl_confidence_{dk}")
            sources = st.session_state.get(f"sql_nl_sources_{dk}") or []
            if confidence or sources:
                src_txt = " · ".join(sources[:5]) if sources else "—"
                st.caption(f"Confianza: {confidence or '—'} · Fuentes: {src_txt}")

            heuristic_sql = st.session_state.get(f"sql_nl_heuristic_{dk}")
            current_sql = st.session_state.get(_editor_key(dk), "")
            if used_llm and heuristic_sql and heuristic_sql.strip() != (current_sql or "").strip():
                with st.expander("Comparar con SQL heurístico", expanded=False):
                    st.code(heuristic_sql, language="sql")
                    heu_exp = st.session_state.get(f"sql_nl_heuristic_exp_{dk}")
                    if heu_exp:
                        st.caption(f"Heurístico: {heu_exp}")

        if not is_llm_available():
            st.caption(
                "Usando motor heurístico — activá Ollama o configurá API keys para SQL avanzado con IA."
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
        engine_label = "LLM + RAG" if st.session_state.get(f"sql_nl_used_llm_{dk}") else "Heurístico"
        report_md = build_sql_report_md(
            last_sql,
            result_df,
            ctx,
            nl_prompt=st.session_state.get(f"sql_nl_last_{dk}"),
            nl_engine=engine_label if st.session_state.get(f"sql_nl_last_{dk}") else None,
            nl_explanation=st.session_state.get(f"sql_nl_explanation_{dk}"),
            heuristic_sql=st.session_state.get(f"sql_nl_heuristic_{dk}"),
        )
        st.download_button(
            "Exportar reporte MD",
            data=report_md,
            file_name=f"paradigm_sql_{dk[:8]}.md",
            mime="text/markdown",
            help="Informe Markdown con consulta, motor NL→SQL y resultados.",
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
