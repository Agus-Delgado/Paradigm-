"""
Paradigm — Decision Intelligence Laboratory (Streamlit).

Uso:
    pip install -r requirements-app.txt
    streamlit run streamlit_app.py
"""

from __future__ import annotations

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
from app.conversational.flow import render_conversational_page_v2
from app.conversational.types import DatasetContext
from app.forecasting import render_forecasting_tab
from app.ml_predict import render_prediction_tab
from app.plots import (
    attended_vs_billed_chart,
    reconciliation_donut,
    specialty_bar_chart,
    trend_chart,
)
from app.ui import (
    inject_theme,
    render_app_footer,
    render_gap_card,
    render_header,
    render_kpi_grid,
    render_landing_page,
    render_regenerate_section,
    render_sidebar_filters,
    render_theme_toggle,
)


def render_executive_overview(
    tables: dict,
    filters,
) -> None:
    filtered = apply_filters(tables, filters)
    if filtered.empty:
        st.warning("No hay citas para los filtros seleccionados.")
        return

    kpis = compute_kpis(filtered, tables)
    render_kpi_grid(kpis)
    render_gap_card(kpis)

    col_l, col_r = st.columns([3, 2])
    with col_l:
        st.plotly_chart(trend_chart(daily_trend(filtered)), use_container_width=True)
    with col_r:
        st.plotly_chart(
            specialty_bar_chart(specialty_breakdown(filtered)),
            use_container_width=True,
        )


def render_reconciliation(tables: dict, filters) -> None:
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

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Citas atendidas (filtro)", attended)
    c2.metric("ATTENDED_NO_BILLING", gap_n)
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
    c3.metric("Con facturación", with_billing)
    c4.metric("Con pendiente", pending)

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
    st.header("Governance & Improvement")
    st.info(
        "Centraliza riesgos, limitaciones, evaluaciones, decisiones y mejoras de Paradigm."
    )

    st.subheader("Risks")
    st.markdown(
        "- duplicacion entre componentes legacy y actuales;\n"
        "- documentacion historica acumulada;\n"
        "- dependencia de archivos y rutas locales;\n"
        "- respuestas generativas no siempre verificables."
    )

    st.subheader("Limitations")
    st.markdown(
        "- uso personal y local;\n"
        "- sin colaboracion multiusuario;\n"
        "- sin persistencia remota;\n"
        "- modulos futuros todavia no implementados."
    )

    st.subheader("Improvement Backlog")
    st.markdown(
        "- [ ] Paradigm Copilot;\n"
        "- [ ] Automation Lab;\n"
        "- [ ] consolidacion de componentes legacy;\n"
        "- [ ] trazabilidad de experimentos;\n"
        "- [ ] evaluacion de respuestas generativas."
    )

    st.subheader("Principles")
    st.markdown(
        "- aprobacion humana;\n"
        "- ejecucion local cuando sea posible;\n"
        "- bajo costo;\n"
        "- trazabilidad;\n"
        "- modularidad."
    )
    st.caption("Primera vista estatica para gobierno, riesgos e improvement planning.")


def render_automation_lab() -> None:
    st.header("Automation Lab")
    st.info(
        "Este espacio concentrara automatizaciones reproducibles, controles y trazabilidad."
    )

    st.subheader("Automation Lifecycle")
    st.markdown(
        "- Trigger\n"
        "- Input\n"
        "- Validation\n"
        "- Action\n"
        "- Approval\n"
        "- Result\n"
        "- History"
    )

    st.subheader("Potential Automations")
    st.markdown(
        "- actualizar datasets locales;\n"
        "- ejecutar controles de calidad;\n"
        "- regenerar reportes;\n"
        "- ejecutar experimentos;\n"
        "- comparar metricas;\n"
        "- detectar fallos en pipelines."
    )

    st.subheader("Safety Controls")
    st.markdown(
        "- aprobacion antes de acciones sensibles;\n"
        "- modo simulacion;\n"
        "- registro de errores;\n"
        "- ejecucion idempotente;\n"
        "- posibilidad de cancelar o revertir."
    )

    st.subheader("Current Status")
    st.markdown(
        "- modulo estructural inicial;\n"
        "- sin automatizaciones activas;\n"
        "- sin scheduler;\n"
        "- sin ejecucion automatica;\n"
        "- sin persistencia propia."
    )
    st.caption("Vista base para futuras automatizaciones, controles y trazabilidad.")


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
        initial_sidebar_state="expanded",
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

    render_header()
    render_regenerate_section()

    pages = {
        "overview": "Overview · Executive Overview",
        "data_quality": "Data & Quality · Conciliación",
        "no_show": "Intelligence · No-Show ML",
        "forecasting": "Intelligence · Forecasting",
        "conversational": "Language & Decisions · AI Conversational Insights",
        "governance": "Governance · Risks & Improvement",
        "automations": "Automation · Automation Lab",
        "copilot": "Copilot · SQL, Python & Data Science",
    }
    page_labels = list(pages.values())
    selected_page_label = st.sidebar.radio(
        "Navegación",
        page_labels,
        label_visibility="collapsed",
    )
    page = next(
        (page_id for page_id, label in pages.items() if label == selected_page_label),
        None,
    )

    if page in ("overview", "data_quality"):
        filters = render_sidebar_filters(tables["appointments"])
    else:
        filters = None

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Mart: `{DB_PATH.name}` · {len(tables['appointments'])} citas")

    if page == "overview":
        render_executive_overview(tables, filters)
    elif page == "data_quality":
        render_reconciliation(tables, filters)
    elif page == "no_show":
        render_prediction_tab(tables, str(DB_PATH), db_mtime)
    elif page == "forecasting":
        render_forecasting_tab(tables, str(DB_PATH), db_mtime)
    elif page == "conversational":
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
        render_governance_improvement()
    elif page == "automations":
        render_automation_lab()
    elif page == "copilot":
        render_copilot_page()
    else:
        st.error("La página seleccionada no es válida.")

    render_app_footer()


if __name__ == "__main__":
    main()
