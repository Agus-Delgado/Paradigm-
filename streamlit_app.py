"""
Paradigm — Decision Intelligence Laboratory (Streamlit).

Uso:
    pip install -r requirements-app.txt
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

# Raíz del repo + paquete paradigm en PYTHONPATH
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "python" / "src"))

import streamlit as st

from paradigm.io.paths import DB_PATH

from app.data import (
    apply_filters,
    attended_no_billing_detail,
    compute_kpis,
    daily_trend,
    ensure_db,
    get_db_mtime,
    load_analyst_csv,
    load_analyst_demo_csv,
    load_mart_tables,
    monthly_attended_vs_billed,
    prepare_dataset_context,
    reconciliation_summary,
    specialty_breakdown,
)
from app.conversational.copilot_ui import render_copilot_page
from app.conversational.flow import render_conversational_page_v2, route_paradigm_task
from app.conversational.types import DatasetContext
from app.forecasting import render_forecasting_tab
from app.ml_predict import render_prediction_tab
from app.plots import (
    attended_vs_billed_chart,
    reconciliation_donut,
    specialty_bar_chart,
    trend_chart,
)
from app.config import SYNTHETIC_BANNER, get_llm_settings
from app.ui import (
    inject_theme,
    get_recent_tasks,
    navigate_to,
    push_recent_task,
    render_app_footer,
    render_cognitive_sequence,
    render_data_quality_process,
    render_global_topbar,
    render_home_core_and_context,
    render_home_launcher,
    render_home_mark_bar,
    render_home_results,
    render_home_surface_styles,
    render_landing_page,
    render_module_context,
    render_page_header,
    render_regenerate_section,
    render_sidebar_filters,
    render_theme_toggle,
)

# ── Observatory navigation (4 spaces → 8 page ids) ───────────────────────────

_SPACE_KEY = "paradigm_active_space"
_VIEW_KEY = "paradigm_active_view"

_SPACES = ("Home", "Assistant", "Workspaces", "System")

_SPACE_VIEWS: dict[str, tuple[str, ...]] = {
    "Home": (),
    "Assistant": ("Paradigm Assistant", "Copilot"),
    "Workspaces": ("Data & Quality", "No-Show Intelligence", "Forecasting"),
    "System": ("Automation Lab", "Governance & Improvement"),
}

_VIEW_TO_PAGE: dict[str, str] = {
    "Paradigm Assistant": "conversational",
    "Copilot": "copilot",
    "Data & Quality": "data_quality",
    "No-Show Intelligence": "no_show",
    "Forecasting": "forecasting",
    "Automation Lab": "automations",
    "Governance & Improvement": "governance",
}

_PAGE_META: dict[str, dict[str, str]] = {
    "overview": {
        "eyebrow": "Home",
        "title": "Paradigm Home",
        "description": "Cognitive laboratory: discover a task, follow the sequence, act on real mart signals.",
        "stage": "Signal",
    },
    "data_quality": {
        "eyebrow": "Workspaces",
        "title": "Data & Quality",
        "description": "Conciliación atención–facturación y detalle de brechas auditables.",
        "stage": "Structure",
    },
    "no_show": {
        "eyebrow": "Workspaces",
        "title": "No-Show Intelligence",
        "description": "Priorización de riesgo, explicación y opciones de intervención.",
        "stage": "Interpretation",
    },
    "forecasting": {
        "eyebrow": "Workspaces",
        "title": "Forecasting",
        "description": "Demanda futura, backtesting y horizonte planificado.",
        "stage": "Interpretation",
    },
    "conversational": {
        "eyebrow": "Assistant",
        "title": "Paradigm Assistant",
        "description": "De evidencia a interpretación y decisión con contexto de negocio.",
        "stage": "Decision",
    },
    "copilot": {
        "eyebrow": "Assistant",
        "title": "Copilot",
        "description": "Revisión técnica de SQL, Python y errores — sin ejecución automática.",
        "stage": "Action",
    },
    "automations": {
        "eyebrow": "System",
        "title": "Automation Lab",
        "description": "Espacio estructural para automatizaciones reproducibles y controles.",
        "stage": "Action",
    },
    "governance": {
        "eyebrow": "System",
        "title": "Governance & Improvement",
        "description": "Riesgos, límites, principios y backlog de mejora del laboratorio.",
        "stage": "System",
    },
}


def _resolve_page_id(space: str, view: str | None) -> str:
    """Map space + optional secondary view to an existing page id."""
    if space == "Home":
        return "overview"
    if view and view in _VIEW_TO_PAGE:
        return _VIEW_TO_PAGE[view]
    views = _SPACE_VIEWS.get(space, ())
    if views:
        return _VIEW_TO_PAGE.get(views[0], "overview")
    return "overview"


def _ensure_nav_state() -> tuple[str, str | None]:
    """Inicializa space/view sin radios; corrige vistas inválidas."""
    if _SPACE_KEY not in st.session_state:
        st.session_state[_SPACE_KEY] = "Home"
    space = str(st.session_state.get(_SPACE_KEY) or "Home")
    if space not in _SPACES:
        space = "Home"
        st.session_state[_SPACE_KEY] = space

    views = _SPACE_VIEWS.get(space, ())
    raw_view = st.session_state.get(_VIEW_KEY)
    view: str | None = str(raw_view).strip() if raw_view else None
    if space == "Home":
        view = None
    elif views:
        if view not in views:
            view = views[0]
            st.session_state[_VIEW_KEY] = view
    else:
        view = None
    return space, view


def _section_label(space: str) -> str:
    """Etiqueta de sección en chrome (Workspaces → Work)."""
    return "Work" if space == "Workspaces" else space


def _render_secondary_sidebar(*, db_name: str, appointment_count: int) -> str:
    """Sidebar de contexto: dataset, vistas del espacio, recientes."""
    space, view = _ensure_nav_state()
    provider = get_llm_settings().provider
    dataset_label = f"SQLite · {db_name} · {appointment_count:,} citas"

    st.sidebar.markdown(
        f"""
        <div class="pd-side-context">
          <div class="pd-side-context__label">Dataset activo</div>
          <div class="pd-side-context__value">{dataset_label}</div>
          <div class="pd-side-context__meta">Local · LLM {provider}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    views = _SPACE_VIEWS.get(space, ())
    if views:
        st.sidebar.markdown(
            '<div class="pd-nav-label">Vistas</div>',
            unsafe_allow_html=True,
        )
        for v in views:
            is_on = view == v
            key = f"pd_side_view_{space}_{v}".replace(" ", "_").replace("&", "and")
            if st.sidebar.button(
                v,
                key=key,
                use_container_width=True,
                type="primary" if is_on else "secondary",
            ):
                navigate_to(space, v)

    recent = get_recent_tasks()
    st.sidebar.markdown(
        '<div class="pd-nav-label">Recientes</div>',
        unsafe_allow_html=True,
    )
    if not recent:
        st.sidebar.caption("Sin tareas en esta sesión.")
    else:
        for i, task in enumerate(recent):
            preview = task if len(task) <= 42 else task[:39] + "…"
            if st.sidebar.button(
                preview,
                key=f"pd_recent_task_{i}",
                use_container_width=True,
                help=task,
            ):
                st.session_state["paradigm_pending_task"] = task
                push_recent_task(task)
                navigate_to("Assistant", "Paradigm Assistant")

    return _resolve_page_id(space, view)


def _render_page_chrome(page_id: str, *, status: str = "Active") -> None:
    """Header mineral compartido; reemplaza el chrome Observatory."""
    meta = _PAGE_META.get(
        page_id,
        {
            "eyebrow": "Paradigm",
            "title": "Vista",
            "description": "",
            "stage": "System",
        },
    )
    section = _section_label(meta["eyebrow"])
    render_page_header(
        section=section,
        title=meta["title"],
        purpose=meta["description"],
        stage=meta["stage"],
        status=status,
    )
    st.caption(SYNTHETIC_BANNER)


def render_executive_overview(
    tables: dict,
    filters,
) -> None:
    """Home: composición del prototipo neural con datos y navegación reales."""
    filtered = apply_filters(tables, filters)
    kpis = None if filtered.empty else compute_kpis(filtered, tables)
    llm_provider = get_llm_settings().provider
    pending = str(st.session_state.get("paradigm_pending_task") or "").strip()
    lit = bool(st.session_state.get("paradigm_home_sequence_lit") or pending)

    render_home_surface_styles()
    render_home_mark_bar()
    render_home_core_and_context(
        filters=filters,
        db_name=DB_PATH.name,
        llm_provider=llm_provider,
        appointment_count=len(tables["appointments"]),
        filtered_rows=len(filtered),
    )
    render_cognitive_sequence(lit=lit)
    render_home_launcher()
    render_home_results(kpis=kpis, task=pending)

    if kpis is not None:
        st.markdown(
            '<div class="pd-home-flow-eyebrow">Evidence charts</div>',
            unsafe_allow_html=True,
        )
        col_l, col_r = st.columns([3, 2])
        with col_l:
            st.plotly_chart(trend_chart(daily_trend(filtered)), use_container_width=True)
        with col_r:
            st.plotly_chart(
                specialty_bar_chart(specialty_breakdown(filtered)),
                use_container_width=True,
            )


def render_reconciliation(tables: dict, filters) -> None:
    render_module_context(
        name="Data & Quality",
        stage="Structure",
        purpose="Conciliar atención y facturación del mart, con detalle auditable de brechas.",
        status="Active",
        capabilities=(
            "Filtros por fecha, especialidad, proveedor y canal",
            "Métricas de conciliación ATTENDED_*",
            "Donut y serie atendidas vs facturadas",
            "Tabla de detalle ATTENDED_NO_BILLING",
        ),
        limitations=(
            "Depende del mart SQLite local filtrado",
            "No corrige datos ni escribe de vuelta al origen",
            "Brechas ilustrativas sobre datos sintéticos",
        ),
    )

    filtered = apply_filters(tables, filters)
    if filtered.empty:
        st.warning("No hay citas para los filtros seleccionados.")
        return

    summary = reconciliation_summary(filtered, tables)
    attended = int((filtered["status_code"] == "ATTENDED").sum())
    gap_n = int(
        summary.loc[summary["reconciliation_bucket"] == "ATTENDED_NO_BILLING", "count"].sum()
        if not summary.empty
        else 0
    )

    if not summary.empty:
        with_billing = int(
            summary.loc[
                summary["reconciliation_bucket"] == "ATTENDED_WITH_BILLING", "count"
            ].sum()
        )
        pending = int(
            summary.loc[
                summary["reconciliation_bucket"] == "ATTENDED_WITH_PENDING", "count"
            ].sum()
        )
    else:
        with_billing = pending = 0

    render_data_quality_process(
        attended=attended,
        gap_n=gap_n,
        with_billing=with_billing,
        pending=pending,
    )

    st.markdown(
        f"""
        <div class="pd-dq-metrics">
          <div class="pd-dq-metric">
            <span class="pd-dq-metric__label">Atendidas</span>
            <span class="pd-dq-metric__value">{attended:,}</span>
          </div>
          <div class="pd-dq-metric pd-dq-metric--risk">
            <span class="pd-dq-metric__label">ATTENDED_NO_BILLING</span>
            <span class="pd-dq-metric__value">{gap_n:,}</span>
          </div>
          <div class="pd-dq-metric">
            <span class="pd-dq-metric__label">Con facturación</span>
            <span class="pd-dq-metric__value">{with_billing:,}</span>
          </div>
          <div class="pd-dq-metric">
            <span class="pd-dq-metric__label">Con pendiente</span>
            <span class="pd-dq-metric__value">{pending:,}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(reconciliation_donut(summary), use_container_width=True)
    with col_b:
        st.plotly_chart(
            attended_vs_billed_chart(monthly_attended_vs_billed(filtered, tables)),
            use_container_width=True,
        )

    st.subheader("Detalle ATTENDED_NO_BILLING")
    detail = attended_no_billing_detail(filtered, tables)
    if detail.empty:
        st.success("Sin brechas de facturación en el período filtrado.")
    else:
        show_cols = [
            "appointment_id",
            "appointment_date",
            "specialty_name",
            "provider_label",
            "channel_code",
            "reconciliation_bucket",
            "billing_lines_count",
            "revenue_total_non_void",
        ]
        st.dataframe(
            detail[show_cols],
            use_container_width=True,
            hide_index=True,
        )


def render_governance_improvement() -> None:
    render_module_context(
        name="Governance & Improvement",
        stage="System",
        purpose="Centralizar riesgos, límites, principios y backlog de mejora del laboratorio.",
        status="Structural",
        capabilities=(
            "Inventario estático de risks y limitations",
            "Backlog de improvement planning",
            "Principios operativos (aprobación humana, local-first)",
        ),
        limitations=(
            "Sin ejecución de controles",
            "Sin persistencia propia ni workflow",
            "Contenido documental, no operativo",
        ),
    )
    st.caption("Módulo estructural: no ejecuta auditorías ni guarda estado.")

    risks = [
        "duplicacion entre componentes legacy y actuales",
        "documentacion historica acumulada",
        "dependencia de archivos y rutas locales",
        "respuestas generativas no siempre verificables",
    ]
    decisions = [
        "aprobacion humana antes de acciones sensibles",
        "ejecucion local cuando sea posible",
        "salidas generativas con revision humana",
    ]
    improvements = [
        "madurar Copilot sin ejecucion automatica",
        "preparar Automation Lab sin scheduler activo",
        "consolidar componentes legacy",
        "mejorar trazabilidad de experimentos",
        "evaluar respuestas generativas",
    ]
    principles = [
        "aprobacion humana",
        "ejecucion local cuando sea posible",
        "bajo costo",
        "trazabilidad",
        "modularidad",
    ]
    backlog = [
        "Paradigm Copilot",
        "Automation Lab",
        "consolidacion de componentes legacy",
        "trazabilidad de experimentos",
        "evaluacion de respuestas generativas",
    ]
    limitations = [
        "uso personal y local",
        "sin colaboracion multiusuario",
        "sin persistencia remota",
        "modulos futuros todavia no implementados",
    ]

    def _items(rows: list[str]) -> str:
        return "".join(f"<li>{html.escape(r)}</li>" for r in rows)

    flow_html = (
        '<div class="pd-gov-flow">'
        '<div class="pd-gov-flow__eyebrow">Governance sequence</div>'
        '<div class="pd-gov-rail" role="list">'
        f'<section class="pd-gov-node pd-gov-node--risk" role="listitem">'
        f'<span class="pd-gov-node__tone">Risks</span>'
        f'<span class="pd-gov-node__count">{len(risks)}</span>'
        f'<ul class="pd-gov-node__list">{_items(risks)}</ul>'
        "</section>"
        '<div class="pd-gov-rail__link" aria-hidden="true"></div>'
        f'<section class="pd-gov-node pd-gov-node--decision" role="listitem">'
        f'<span class="pd-gov-node__tone">Decisions</span>'
        f'<span class="pd-gov-node__count">{len(decisions)}</span>'
        f'<ul class="pd-gov-node__list">{_items(decisions)}</ul>'
        "</section>"
        '<div class="pd-gov-rail__link" aria-hidden="true"></div>'
        f'<section class="pd-gov-node pd-gov-node--improve" role="listitem">'
        f'<span class="pd-gov-node__tone">Improvements</span>'
        f'<span class="pd-gov-node__count">{len(improvements)}</span>'
        f'<ul class="pd-gov-node__list">{_items(improvements)}</ul>'
        "</section>"
        "</div>"
        "</div>"
    )
    st.markdown(flow_html, unsafe_allow_html=True)

    secondary = (
        '<div class="pd-gov-secondary">'
        '<section class="pd-gov-block">'
        '<div class="pd-gov-block__label">Principles</div>'
        f'<ul class="pd-gov-block__list">{_items(principles)}</ul>'
        "</section>"
        '<section class="pd-gov-block pd-gov-block--backlog">'
        '<div class="pd-gov-block__label">Backlog</div>'
        '<div class="pd-gov-backlog">'
        + "".join(
            '<div class="pd-gov-backlog__item">'
            '<span class="pd-gov-backlog__mark" aria-hidden="true">[ ]</span>'
            f"<span>{html.escape(item)}</span></div>"
            for item in backlog
        )
        + "</div>"
        "</section>"
        '<section class="pd-gov-block pd-gov-block--limits">'
        '<div class="pd-gov-block__label">Limitations</div>'
        f'<ul class="pd-gov-block__list">{_items(limitations)}</ul>'
        "</section>"
        "</div>"
    )
    st.markdown(secondary, unsafe_allow_html=True)


def render_automation_lab() -> None:
    render_module_context(
        name="Automation Lab",
        stage="Action",
        purpose="Espacio para automatizaciones reproducibles, controles y trazabilidad futura.",
        status="Structural",
        capabilities=(
            "Ciclo de vida propuesto (trigger → approval → history)",
            "Catálogo de automatizaciones potenciales",
            "Controles de seguridad previstos",
        ),
        limitations=(
            "Sin scheduler ni ejecución automática",
            "Sin persistencia de runs",
            "Sin acciones reales sobre datos o sistemas",
        ),
    )
    st.caption("Módulo estructural: no ejecuta jobs ni persiste historial.")

    stages = (
        ("Trigger", "structure", "planned", "Evento o schedule futuro"),
        ("Validate", "structure", "structural", "Controles previstos"),
        ("Approve", "decision", "structural", "Aprobación humana requerida"),
        ("Execute", "structure", "inactive", "Sin scheduler ni runs activos"),
        ("Observe", "interpretation", "planned", "Historial aún no persistido"),
    )
    nodes: list[str] = []
    for i, (label, tone, status, detail) in enumerate(stages):
        if i:
            nodes.append('<div class="pd-auto-link" aria-hidden="true"></div>')
        nodes.append(
            f'<div class="pd-auto-step pd-auto-step--{tone} pd-auto-step--{status}" '
            f'style="--i:{i}">'
            f'<span class="pd-auto-step__label">{html.escape(label)}</span>'
            f'<span class="pd-auto-step__status">{html.escape(status)}</span>'
            f'<span class="pd-auto-step__detail">{html.escape(detail)}</span>'
            "</div>"
        )
    pipeline_html = (
        '<div class="pd-auto-flow">'
        '<div class="pd-auto-flow__eyebrow">Automation pipeline</div>'
        f'<div class="pd-auto-rail" role="list">{"".join(nodes)}</div>'
        "</div>"
    )
    st.markdown(pipeline_html, unsafe_allow_html=True)

    catalog = (
        '<div class="pd-auto-catalog">'
        '<section class="pd-auto-block">'
        '<div class="pd-auto-block__label">Potential Automations</div>'
        '<ul class="pd-auto-block__list">'
        "<li>actualizar datasets locales</li>"
        "<li>ejecutar controles de calidad</li>"
        "<li>regenerar reportes</li>"
        "<li>ejecutar experimentos</li>"
        "<li>comparar metricas</li>"
        "<li>detectar fallos en pipelines</li>"
        "</ul>"
        "</section>"
        '<section class="pd-auto-block pd-auto-block--safety">'
        '<div class="pd-auto-block__label">Safety Controls</div>'
        '<ul class="pd-auto-block__list">'
        "<li>aprobacion antes de acciones sensibles</li>"
        "<li>modo simulacion</li>"
        "<li>registro de errores</li>"
        "<li>ejecucion idempotente</li>"
        "<li>posibilidad de cancelar o revertir</li>"
        "</ul>"
        "</section>"
        '<section class="pd-auto-block pd-auto-block--status">'
        '<div class="pd-auto-block__label">Current Status</div>'
        '<ul class="pd-auto-block__list">'
        "<li>modulo estructural inicial</li>"
        "<li>sin automatizaciones activas</li>"
        "<li>sin scheduler</li>"
        "<li>sin ejecucion automatica</li>"
        "<li>sin persistencia propia</li>"
        "</ul>"
        "</section>"
        "</div>"
    )
    st.markdown(catalog, unsafe_allow_html=True)


def _prepare_analyst_context(
    mode: str,
    tables: dict | None = None,
    uploaded=None,
    *,
    synthetic_domain: str = "healthcare",
) -> DatasetContext | None:
    from app.conversational.synthetic import generate_synthetic_dataset, synthetic_source_label

    if mode == "demo":
        df, err = load_analyst_demo_csv()
        if df is None:
            st.error(err or "No se pudo cargar el demo.")
            return None
        return prepare_dataset_context(df, source="demo", source_label="Demo consultorio")
    if mode == "synthetic":
        df = generate_synthetic_dataset(synthetic_domain)  # type: ignore[arg-type]
        label = synthetic_source_label(synthetic_domain)  # type: ignore[arg-type]
        return prepare_dataset_context(df, source="synthetic", source_label=label)
    if mode == "upload":
        df, err = load_analyst_csv(uploaded)
        if df is None:
            st.error(err or "Error al cargar el archivo.")
            return None
        name = getattr(uploaded, "name", "archivo") or "archivo"
        return prepare_dataset_context(df, source="upload", source_label=name)
    return None


def main() -> None:
    st.set_page_config(
        page_title="Paradigm — Decision Intelligence Laboratory",
        page_icon="◈",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    dark_mode = render_theme_toggle()
    inject_theme(dark_mode)

    # ── Landing page gate ──────────────────────────────────────────────────
    # First visit (or after logout) shows the immersive landing hero.
    # render_landing_page() calls st.rerun() after the Enter button is clicked,
    # which sets show_landing=False and drops through to the main app below.
    if st.session_state.get("show_landing", True):
        render_landing_page()
        st.stop()

    if not ensure_db(DB_PATH):
        st.stop()

    db_mtime = get_db_mtime(DB_PATH)
    tables = load_mart_tables(str(DB_PATH), db_mtime)

    space, _view = _ensure_nav_state()
    render_global_topbar(space)
    page = _render_secondary_sidebar(
        db_name=DB_PATH.name,
        appointment_count=len(tables["appointments"]),
    )

    if page in ("overview", "data_quality"):
        with st.sidebar.expander("Filtros", expanded=(page == "data_quality")):
            filters = render_sidebar_filters(tables["appointments"])
    else:
        filters = None

    with st.sidebar.expander("Mantenimiento", expanded=False):
        render_regenerate_section()

    if page == "overview":
        st.caption(SYNTHETIC_BANNER)
        render_executive_overview(tables, filters)
    elif page == "data_quality":
        _render_page_chrome(page)
        render_reconciliation(tables, filters)
    elif page == "no_show":
        _render_page_chrome(page)
        render_module_context(
            name="No-Show Intelligence",
            stage="Interpretation",
            purpose="Priorizar riesgo de ausentismo, explicar predicciones y explorar impacto.",
            status="Active",
            capabilities=(
                "Modelos no-show entrenados sobre mart sintético",
                "Explicabilidad SHAP local/global",
                "Simulación de impacto y motor prescriptivo",
            ),
            limitations=(
                "No es producción clínica",
                "Métricas pueden ser débiles en sintético",
                "Requiere artefactos ML previos en disco",
            ),
        )
        render_prediction_tab(tables, str(DB_PATH), db_mtime)
    elif page == "forecasting":
        _render_page_chrome(page)
        render_module_context(
            name="Forecasting",
            stage="Interpretation",
            purpose="Proyectar demanda de citas con backtesting y registro de experimentos.",
            status="Active",
            capabilities=(
                "Entrenamiento de modelos de demanda",
                "Selección y resumen de runs recientes",
                "Charts de historia, horizonte y backtest",
            ),
            limitations=(
                "Depende de runs locales en ml/experiments",
                "No despliega forecast a producción",
                "Especialidades/horizontes acotados al experimento",
            ),
        )
        render_forecasting_tab(tables, str(DB_PATH), db_mtime)
    elif page == "conversational":
        _render_page_chrome(page)
        pending_task = st.session_state.get("paradigm_pending_task")
        if isinstance(pending_task, str) and pending_task.strip():
            preview = route_paradigm_task(pending_task)
            st.caption(
                f"Pending route · **{preview['destination']}** · confidence `{preview['confidence']}`"
            )

        analyst_ctx: DatasetContext | None = st.session_state.get("analyst_v2_ctx")

        def on_prepare(mode: str, uploaded=None, synthetic_domain: str = "healthcare"):
            ctx = _prepare_analyst_context(
                mode,
                uploaded=uploaded,
                synthetic_domain=synthetic_domain,
            )
            if ctx is not None:
                st.session_state["analyst_v2_ctx"] = ctx
            return ctx

        render_conversational_page_v2(analyst_ctx, on_prepare=on_prepare)
        from app.conversational.ai_analyst_ui import render_ai_analyst_sidebar_controls

        render_ai_analyst_sidebar_controls()
    elif page == "governance":
        _render_page_chrome(page)
        render_governance_improvement()
    elif page == "automations":
        _render_page_chrome(page)
        render_automation_lab()
    elif page == "copilot":
        _render_page_chrome(page)
        render_copilot_page()
    else:
        _render_page_chrome(page)
        st.error("La página seleccionada no es válida.")

    render_app_footer()


if __name__ == "__main__":
    main()
