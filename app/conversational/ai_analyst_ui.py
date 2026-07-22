"""UI compartida del Conversational Analyst (LLM + chat persistente)."""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import streamlit as st

from app.config import COLOR_MUTED, COLOR_PRIMARY_SOFT, COLOR_SUCCESS, COLOR_WARNING
from app.config.llm_config import get_llm_settings, is_llm_available
from app.conversational.llm_logging import get_log_path, read_log_entries
from app.conversational.llm_service import (
    AnalystResult,
    analyst_result_to_dict,
    generate_insights,
)
from app.conversational.plots import build_sql_result_chart
from app.conversational.sql_engine import execute_sql_on_dataframe
from app.conversational.types import DatasetContext

_PANEL_KEY = "ai_analyst_panel_open_{dk}"
_CHAT_KEY = "ai_analyst_chat_{dk}"
_SIDEBAR_HIST_KEY = "ai_analyst_show_log_history"

_PROVIDER_LABELS = {
    "ollama": "Ollama local",
    "groq": "Groq API",
    "openai": "OpenAI API",
    "grok": "Grok (xAI) API",
    "disabled": "Heurístico",
}

_IMPACT_BADGE = {
    "Alto": "badge-high",
    "Medio": "badge-medium",
    "Bajo": "badge-low",
    "High": "badge-high",
    "Medium": "badge-medium",
    "Low": "badge-low",
}

_CONFIDENCE_LABEL = {
    "high": "Alta",
    "medium": "Media",
    "low": "Baja",
}


def panel_open_key(dataset_key: str) -> str:
    return _PANEL_KEY.format(dk=dataset_key)


def chat_history_key(dataset_key: str) -> str:
    return _CHAT_KEY.format(dk=dataset_key)


def build_wizard_llm_query(answers: dict[str, str | float]) -> str:
    parts: list[str] = []
    objective = str(answers.get("objective", "")).strip()
    if objective:
        parts.append(f"Objetivo de negocio: {objective}")
    for key, label in (
        ("hypothesis", "Hipótesis de causa"),
        ("suspect_segment", "Segmento sospechoso"),
        ("segment", "Segmento sospechoso"),
    ):
        val = str(answers.get(key, "")).strip()
        if val and val not in ("—", "-"):
            parts.append(f"{label}: {val}")
    return " | ".join(parts) if parts else "Exploración general del dataset activo."


def fetch_llm_insight(
    ctx: DatasetContext,
    query: str,
    *,
    sql_result: pd.DataFrame | None = None,
) -> tuple[AnalystResult, pd.DataFrame | None]:
    """Ejecuta generate_insights y opcionalmente corre el SQL sugerido."""
    result = generate_insights(
        query,
        ctx.df,
        logical_types=ctx.logical_types,
        sql_result=sql_result,
    )
    sql_df: pd.DataFrame | None = None
    if result.sql and sql_result is None:
        sql_df, err = execute_sql_on_dataframe(ctx.df, result.sql)
        if err:
            sql_df = None
    return result, sql_df


def llm_spinner_message() -> str:
    """Mensaje de loading contextual según proveedor."""
    cfg = get_llm_settings()
    if cfg.provider == "disabled" or not is_llm_available():
        return "Analizando con motor heurístico (sin LLM)…"
    label = _PROVIDER_LABELS.get(cfg.provider, cfg.provider)
    return f"El AI Analyst está pensando ({label})…"


def render_llm_status_banner() -> None:
    """Banner de estado del proveedor LLM con tooltip nativo HTML."""
    cfg = get_llm_settings()
    tip = (
        "El AI Analyst usa RAG sobre docs/métricas/SQL samples + schema del dataset. "
        "Solo genera SQL de lectura (SELECT/WITH). Máx. consultas/min según PARADIGM_LLM_RATE_LIMIT."
    )
    if cfg.provider == "disabled":
        st.markdown(
            f'<div class="ai-llm-banner ai-llm-banner--muted" title="{tip}">'
            f'<span class="ai-llm-banner__icon">◇</span> '
            f"Motor heurístico activo — configurá <code>PARADIGM_LLM_PROVIDER=ollama</code> "
            f"o una API key para IA avanzada."
            f"</div>",
            unsafe_allow_html=True,
        )
        return
    if is_llm_available():
        st.markdown(
            f'<div class="ai-llm-banner ai-llm-banner--live" title="{tip}">'
            f'<span class="ai-llm-banner__icon">✦</span> '
            f"AI Analyst conectado · <strong>{cfg.provider}</strong> · <code>{cfg.model}</code>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="ai-llm-banner ai-llm-banner--warn" title="{tip}">'
            f'<span class="ai-llm-banner__icon">⚠</span> '
            f"Usando motor heurístico — activá Ollama o configurá API keys para IA avanzada."
            f"</div>",
            unsafe_allow_html=True,
        )
    st.caption("Hover sobre el banner para ver cómo funciona el grounding y los límites de seguridad.")


def render_ask_ai_analyst_button(ctx: DatasetContext, *, tab_suffix: str) -> None:
    """Botón destacado para abrir/cerrar el panel de chat AI."""
    dk = ctx.dataset_key
    key = panel_open_key(dk)
    is_open = st.session_state.get(key, False)
    label = "✦ Cerrar AI Analyst" if is_open else "✦ Ask AI Analyst"
    if st.button(
        label,
        type="primary",
        use_container_width=True,
        key=f"ask_ai_analyst_{tab_suffix}_{dk}",
        help="Chat persistente con el analista LLM (RAG + insights estructurados).",
    ):
        st.session_state[key] = not is_open
        st.rerun()


def render_llm_insight_card(
    payload: dict[str, Any],
    *,
    title: str = "Insight del AI Analyst",
    sql_df: pd.DataFrame | None = None,
    show_sql: bool = True,
) -> None:
    """Tarjeta premium: insight, recomendación, impacto, fuentes y gráfico opcional."""
    used_llm = payload.get("used_llm", False)
    engine_label = "LLM + RAG" if used_llm else "Heurístico"
    engine_cls = "ai-engine-badge--llm" if used_llm else "ai-engine-badge--heuristic"

    st.markdown(
        f'<div class="ai-insight-header">'
        f'<span class="ai-insight-title">{title}</span>'
        f'<span class="ai-engine-badge {engine_cls}">{engine_label}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )

    confidence = _CONFIDENCE_LABEL.get(str(payload.get("confidence", "low")), "Baja")
    impact = str(payload.get("business_impact", "Medio"))
    badge_cls = _IMPACT_BADGE.get(impact, "badge-medium")

    c1, c2 = st.columns(2)
    c1.metric("Confianza", confidence)
    c2.markdown(
        f'<div style="margin-top:0.5rem;">'
        f'<span style="color:{COLOR_MUTED};font-size:0.85rem;">Impacto</span><br/>'
        f'<span class="{badge_cls}" style="margin-top:0.25rem;display:inline-block;">{impact}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="insight-card" style="background:rgba(94,200,212,0.06);">'
        f'<strong style="color:{COLOR_PRIMARY_SOFT};">Insight</strong><br/>'
        f'{payload.get("insight", "")}</div>',
        unsafe_allow_html=True,
    )

    recommendation = payload.get("recommendation")
    if recommendation:
        st.markdown(
            f'<div class="insight-card">'
            f'<strong style="color:{COLOR_SUCCESS};">Recomendación</strong><br/>'
            f"{recommendation}</div>",
            unsafe_allow_html=True,
        )

    sources = payload.get("sources") or []
    if sources:
        src_html = " · ".join(f"<code>{s}</code>" for s in sources[:8])
        st.markdown(
            f'<p style="color:{COLOR_MUTED};font-size:0.82rem;margin-top:0.5rem;">'
            f"<strong>Fuentes:</strong> {src_html}</p>",
            unsafe_allow_html=True,
        )

    if payload.get("fallback_reason") and not used_llm:
        st.caption(f"Fallback: {payload['fallback_reason']}")

    if show_sql and payload.get("sql"):
        with st.expander("SQL sugerido por el analista", expanded=False):
            st.code(str(payload["sql"]), language="sql")
            if payload.get("explanation"):
                st.caption(payload["explanation"])

    if sql_df is not None and not sql_df.empty:
        st.plotly_chart(build_sql_result_chart(sql_df), use_container_width=True)


def append_chat_turn(dataset_key: str, query: str, payload: dict[str, Any], sql_df: pd.DataFrame | None) -> None:
    hist_key = chat_history_key(dataset_key)
    history = st.session_state.setdefault(hist_key, [])
    history.append(
        {
            "query": query,
            "payload": payload,
            "sql_rows": len(sql_df) if sql_df is not None else 0,
        }
    )
    st.session_state[hist_key] = history[-20:]


def render_ai_analyst_chat_panel(ctx: DatasetContext) -> None:
    """Panel de chat persistente (visible en las 3 pestañas cuando está abierto)."""
    dk = ctx.dataset_key
    st.markdown(
        '<div class="ai-analyst-panel">'
        '<p class="ai-analyst-panel__title">✦ AI Analyst — chat persistente</p>'
        '<p class="ai-analyst-panel__subtitle">Preguntá en lenguaje natural · grounding con RAG + schema</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    history = st.session_state.get(chat_history_key(dk), [])
    for i, turn in enumerate(reversed(history[-5:])):
        with st.container(border=True):
            st.markdown(f"**Vos:** {turn['query']}")
            render_llm_insight_card(
                turn["payload"],
                title=f"Respuesta #{len(history) - i}",
                show_sql=True,
            )
            if turn.get("sql_rows"):
                st.caption(f"SQL ejecutado: {turn['sql_rows']} filas devueltas.")

    with st.form(f"ai_analyst_chat_form_{dk}", clear_on_submit=True):
        query = st.text_area(
            "Tu pregunta al analista",
            placeholder="Ej.: ¿Dónde se concentra el no-show? ¿Qué especialidad tiene mayor brecha de facturación?",
            height=88,
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Enviar al AI Analyst", use_container_width=True)

    if submitted and query.strip():
        with st.spinner(llm_spinner_message()):
            result, sql_df = fetch_llm_insight(ctx, query.strip())
        append_chat_turn(dk, query.strip(), analyst_result_to_dict(result), sql_df)
        st.rerun()


def render_ai_workspace_chrome(ctx: DatasetContext, *, tab_suffix: str) -> None:
    """Banner LLM + botón Ask AI Analyst + panel opcional."""
    col_banner, col_btn = st.columns([3, 1])
    with col_banner:
        render_llm_status_banner()
    with col_btn:
        render_ask_ai_analyst_button(ctx, tab_suffix=tab_suffix)

    if st.session_state.get(panel_open_key(ctx.dataset_key), False):
        st.markdown('<div class="ai-analyst-panel-wrap">', unsafe_allow_html=True)
        render_ai_analyst_chat_panel(ctx)
        st.markdown("</div>", unsafe_allow_html=True)


def render_ai_analyst_sidebar_controls() -> None:
    """Controles sidebar: toggle historial JSONL (debug / transparencia)."""
    debug_env = os.getenv("PARADIGM_DEBUG", "").strip().lower() in ("1", "true", "yes")
    st.sidebar.markdown("### AI Analyst")
    show_default = st.session_state.get(_SIDEBAR_HIST_KEY, debug_env)
    show_hist = st.sidebar.toggle(
        "Ver Historial AI",
        value=show_default,
        help="Muestra las últimas interacciones del log JSONL (queries, respuestas, latencia, tokens).",
        key="ai_analyst_sidebar_hist_toggle",
    )
    st.session_state[_SIDEBAR_HIST_KEY] = show_hist

    if not show_hist and not debug_env:
        st.sidebar.caption(f"Log: `{get_log_path().name}`")
        return

    entries = read_log_entries(limit=15)
    if not entries:
        st.sidebar.info("Sin entradas en el historial AI aún.")
        return

    st.sidebar.caption(f"Últimas {len(entries)} entradas · `{get_log_path()}`")
    for i, entry in enumerate(entries):
        op = entry.get("operation", "?")
        ok = "✓" if entry.get("success") else "✗"
        ms = entry.get("duration_ms")
        tok = entry.get("tokens_approx", {})
        label = f"{ok} {op}"
        if ms is not None:
            label += f" · {ms}ms"
        with st.sidebar.expander(label, expanded=(i == 0 and debug_env)):
            st.caption(entry.get("ts", ""))
            st.markdown(f"**Query:** {str(entry.get('query', ''))[:200]}")
            resp = entry.get("response") or {}
            if resp.get("insight"):
                st.markdown(f"**Insight:** {resp['insight'][:300]}")
            if resp.get("sql"):
                st.code(str(resp["sql"])[:500], language="sql")
            if tok:
                st.caption(f"Tokens ~{tok.get('total', '?')} (in:{tok.get('prompt')} out:{tok.get('completion')})")
            if entry.get("error"):
                st.warning(str(entry["error"]))
