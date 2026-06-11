"""Flujo UI del analista conversacional: landing → preview → wizard → auto-análisis."""

from __future__ import annotations

import streamlit as st

from app.conversational.analysis import run_contextual_analysis
from app.conversational.data_explorer import make_explore_ia_handler, render_data_explorer
from app.conversational.legacy_bridge import run_conversational_analysis
from app.conversational.plan import build_analysis_plan
from app.conversational.plots import build_contextual_plots
from app.conversational.questions import generate_guided_questions
from app.conversational.sql_engine import invalidate_cache as invalidate_sql_cache
from app.conversational.sql_explorer import render_sql_explorer
from app.conversational.synthetic import SyntheticDomain, synthetic_source_label
from app.conversational.types import DatasetContext
from app.ui import (
    render_analyst_progress,
    render_analyst_wizard_banner,
    render_contextual_results,
    render_guided_questionnaire,
    render_schema_brief,
    render_schema_columns_preview,
    render_workspace_header,
)

TAB_GUIDED = "Análisis Guiado"
TAB_SQL = "SQL Explorer"
TAB_EXPLORER = "Data Explorer"
TAB_OPTIONS = (TAB_GUIDED, TAB_SQL, TAB_EXPLORER)


def _answers_key(prefix: str, dataset_key: str) -> str:
    return f"analyst_{prefix}_answers_{dataset_key}"


def _result_key(dataset_key: str) -> str:
    return f"analyst_result_{dataset_key}"


def _skip_key(dataset_key: str) -> str:
    return f"analyst_wizard_skipped_{dataset_key}"


def _pending_run_key(dataset_key: str) -> str:
    return f"analyst_pending_run_{dataset_key}"


def _clear_analyst_session(dataset_key: str | None = None) -> None:
    prefixes = ("analyst_", "sql_", "explorer_")
    for k in list(st.session_state.keys()):
        if any(k.startswith(p) for p in prefixes):
            if dataset_key is None or dataset_key in k:
                del st.session_state[k]
    if dataset_key is None:
        st.session_state.pop("paradigm_ai_history", None)
        st.session_state.pop("analyst_active_tab", None)
    invalidate_sql_cache(dataset_key)


def get_merged_answers(dataset_key: str) -> dict[str, str | float]:
    return dict(st.session_state.get(_answers_key("wizard", dataset_key), {}))


def _set_active_tab(tab: str) -> None:
    st.session_state["analyst_active_tab"] = tab


def _run_analysis(ctx: DatasetContext, answers: dict[str, str | float]) -> None:
    render_analyst_progress("analyzing")
    plan = build_analysis_plan(answers, ctx.domain, ctx.logical_types, df=ctx.df, profile=ctx.profile, findings=ctx.findings)
    result = run_contextual_analysis(
        ctx.df,
        ctx.logical_types,
        ctx.profile,
        ctx.findings,
        answers,
        ctx.domain,
    )
    figures = build_contextual_plots(ctx.df, ctx.logical_types, plan)
    st.session_state[_result_key(ctx.dataset_key)] = {
        "result": result,
        "figures": figures,
        "plan": plan,
    }


def _render_dataset_header(ctx: DatasetContext) -> None:
    st.caption(
        f"**{ctx.source_label}** · dominio `{ctx.domain}` · "
        f"{len(ctx.df):,} filas × {len(ctx.df.columns)} columnas"
    )
    if st.button("← Cambiar dataset", key=f"analyst_header_change_{ctx.dataset_key}"):
        st.session_state.pop("analyst_v2_ctx", None)
        _clear_analyst_session()
        st.rerun()


def _render_tab_nav() -> str:
    active = st.session_state.get("analyst_active_tab", TAB_GUIDED)
    if active not in TAB_OPTIONS:
        active = TAB_GUIDED
    choice = st.radio(
        "Sección",
        TAB_OPTIONS,
        horizontal=True,
        index=TAB_OPTIONS.index(active),
        key="analyst_active_tab",
        label_visibility="collapsed",
    )
    return choice


def _render_followup_chat(ctx: DatasetContext) -> None:
    st.divider()
    st.subheader("Seguimiento conversacional")
    st.caption(
        "Preguntas de seguimiento sobre el dataset activo. "
        "Motor determinístico basado en schema — sin LLM."
    )
    history_key = "paradigm_ai_history"
    if history_key not in st.session_state:
        st.session_state[history_key] = []

    with st.form("analyst_followup_form"):
        query = st.text_input(
            "Tu pregunta",
            placeholder="Ej.: ¿Qué columnas tienen más nulos? ¿Dónde están los outliers en defectos?",
        )
        submitted = st.form_submit_button("Analizar", use_container_width=True)

    if submitted and query.strip():
        with st.spinner("Analizando…"):
            result = run_conversational_analysis(
                query.strip(),
                ctx.df,
                ctx.logical_types,
                ctx.profile,
                findings=ctx.findings,
            )
        st.session_state[history_key].append({"query": query.strip(), "result": result})
        with st.container(border=True):
            st.markdown(f"**{result['title']}**")
            st.caption(result["summary"])
            for item in result.get("findings", [])[:6]:
                st.markdown(f"- {item}")


def _render_guided_tab(ctx: DatasetContext, *, show_ml_cta: bool) -> None:
    dk = ctx.dataset_key
    cached = st.session_state.get(_result_key(dk))
    if not cached:
        st.info(
            "El análisis guiado estará disponible cuando completes el cuestionario "
            "o el procesamiento automático finalice."
        )
        return

    render_workspace_header(
        "Análisis Guiado",
        f"{ctx.source_label} · {len(ctx.df):,} filas",
    )

    render_contextual_results(
        cached["result"],
        cached["figures"],
        show_ml_cta=show_ml_cta and ctx.domain == "healthcare_mart",
        ctx=ctx,
        plan=cached.get("plan"),
    )
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Re-analizar con nuevo contexto", type="primary", key=f"reset_{dk}"):
            for k in list(st.session_state.keys()):
                if dk in k and k.startswith("analyst_"):
                    del st.session_state[k]
            st.session_state.pop(_skip_key(dk), None)
            st.session_state.pop("paradigm_ai_history", None)
            st.rerun()
    with col_b:
        if st.button("Cambiar dataset", key=f"change_ds_{dk}"):
            st.session_state.pop("analyst_v2_ctx", None)
            _clear_analyst_session()
            st.rerun()
    _render_followup_chat(ctx)


def _render_post_analysis_workspace(ctx: DatasetContext, *, show_ml_cta: bool) -> None:
    """Tres pestañas tras wizard/resultados."""
    _render_dataset_header(ctx)
    tab = _render_tab_nav()

    if tab == TAB_GUIDED:
        _render_guided_tab(ctx, show_ml_cta=show_ml_cta)
    elif tab == TAB_SQL:
        render_sql_explorer(ctx)
    else:
        on_ia = make_explore_ia_handler(
            set_active_tab=_set_active_tab,
            skip_key_fn=_skip_key,
            answers_key_fn=_answers_key,
            pending_run_key_fn=_pending_run_key,
        )
        render_data_explorer(ctx, on_explore_ia=on_ia)


def render_analyst_landing(*, on_prepare, show_change_dataset: bool = True) -> DatasetContext | None:
    """Pantalla inicial: elegir fuente y cargar con un solo botón."""
    st.markdown("## Asistente Analítico Paradigm")
    st.markdown("### Análisis Basado en Datos")
    st.caption(
        "Paradigm actúa como un analista senior: primero entiende tu problema de negocio, "
        "luego busca causas raíz en los datos."
    )

    if show_change_dataset and st.session_state.get("analyst_v2_ctx") is not None:
        if st.button("← Cambiar dataset", key="analyst_change_dataset"):
            st.session_state.pop("analyst_v2_ctx", None)
            _clear_analyst_session()
            st.rerun()

    source = st.radio(
        "¿Con qué datos querés comenzar?",
        [
            "Usar Dataset Demo (Consultorio Médico)",
            "Generar Datos Aleatorios de Prueba",
            "Subir mi propio archivo",
        ],
        key="analyst_landing_source",
    )

    synthetic_domain: SyntheticDomain = "healthcare"
    uploaded = None

    if source == "Generar Datos Aleatorios de Prueba":
        domain_choice = st.selectbox(
            "Dominio del dataset sintético",
            options=["healthcare", "finance", "operations"],
            format_func=lambda x: {
                "healthcare": "Salud / consultorio",
                "finance": "Finanzas",
                "operations": "Operaciones / manufactura",
            }[x],
            key="analyst_synthetic_domain",
        )
        synthetic_domain = domain_choice  # type: ignore[assignment]
        st.info(
            "Se generará un dataset con patrones analizables (outliers, segmentos problemáticos) "
            "para probar el flujo completo."
        )
    elif source == "Subir mi propio archivo":
        uploaded = st.file_uploader(
            "Archivo CSV o Excel",
            type=["csv", "xlsx", "xls"],
            key="analyst_landing_upload",
        )

    if st.button("Cargar y Comenzar Análisis", type="primary", use_container_width=True):
        render_analyst_progress("loading")
        with st.spinner("Cargando datos…"):
            if source == "Usar Dataset Demo (Consultorio Médico)":
                ctx = on_prepare("demo")
            elif source == "Generar Datos Aleatorios de Prueba":
                ctx = on_prepare("synthetic", synthetic_domain=synthetic_domain)
            else:
                if uploaded is None:
                    st.warning("Subí un archivo CSV o Excel antes de continuar.")
                    return None
                ctx = on_prepare("upload", uploaded=uploaded)

        if ctx is None:
            return None

        render_analyst_progress("detecting")
        with st.spinner("Detectando estructura…"):
            _clear_analyst_session(ctx.dataset_key)
            st.session_state["analyst_v2_ctx"] = ctx
        st.rerun()

    return st.session_state.get("analyst_v2_ctx")


def render_analyst_flow(ctx: DatasetContext, *, show_ml_cta: bool = False) -> None:
    """Flujo lineal: preview → wizard (max 3Q) → auto-análisis → resultados con tabs."""
    dk = ctx.dataset_key
    wizard_key = _answers_key("wizard", dk)
    result_key = _result_key(dk)
    cached = st.session_state.get(result_key)

    if st.session_state.pop(_pending_run_key(dk), False):
        answers = get_merged_answers(dk)
        if not answers:
            answers = {"objective": "Exploración general del dataset"}
        with st.spinner("Generando análisis contextual…"):
            _run_analysis(ctx, answers)
        st.rerun()

    if cached:
        _render_post_analysis_workspace(ctx, show_ml_cta=show_ml_cta)
        return

    render_analyst_progress("detecting")
    st.subheader("Vista previa del dataset")
    render_schema_brief(ctx)
    render_schema_columns_preview(ctx)

    if st.session_state.get(_skip_key(dk)):
        st.session_state[wizard_key] = {"objective": "Exploración general del dataset"}
        st.session_state[_pending_run_key(dk)] = True
        st.rerun()

    if st.session_state.get(wizard_key):
        render_analyst_progress("understanding")
        st.session_state[_pending_run_key(dk)] = True
        st.rerun()

    render_analyst_progress("questions")
    render_analyst_wizard_banner()

    questions = generate_guided_questions(
        ctx.df,
        ctx.logical_types,
        ctx.domain,
        phase="wizard",
        profile=ctx.profile,
        findings=ctx.findings,
    )
    with st.form(f"analyst_wizard_form_{dk}"):
        st.markdown("**Contexto de negocio** — 2 a 3 preguntas (~1 min)")
        answers = render_guided_questionnaire(questions, key_prefix=f"wizard_{dk}")
        col_a, col_b = st.columns([2, 1])
        with col_a:
            submit = st.form_submit_button(
                "Continuar y analizar",
                type="primary",
                use_container_width=True,
            )
        with col_b:
            skip = st.form_submit_button(
                "Explorar sin cuestionario",
                use_container_width=True,
            )

    if skip:
        st.session_state[_skip_key(dk)] = True
        st.rerun()

    if submit:
        if not str(answers.get("objective", "")).strip():
            st.warning("Indicá al menos el objetivo principal de negocio.")
        else:
            st.session_state[wizard_key] = answers
            render_analyst_progress("understanding")
            st.session_state[_pending_run_key(dk)] = True
            st.rerun()


def render_conversational_page_v2(
    ctx: DatasetContext | None,
    *,
    on_prepare,
) -> None:
    """Página v2: landing limpia + flujo analista."""
    if ctx is None:
        render_analyst_landing(on_prepare=on_prepare)
        return
    render_analyst_flow(ctx, show_ml_cta=True)


# Compatibilidad legacy — delegar al flujo unificado
def render_wizard_optional(ctx: DatasetContext, *, show_skip: bool = True) -> bool:
    """Deprecated: el wizard vive dentro de render_analyst_flow."""
    return bool(
        st.session_state.get(_answers_key("wizard", ctx.dataset_key))
        or st.session_state.get(_skip_key(ctx.dataset_key))
        or st.session_state.get(_result_key(ctx.dataset_key))
    )


def render_insights_tab(ctx: DatasetContext, *, show_ml_cta: bool = False) -> None:
    """Deprecated: usar render_analyst_flow."""
    render_analyst_flow(ctx, show_ml_cta=show_ml_cta)
