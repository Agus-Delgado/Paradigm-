"""
Paradigm Live Demo — app Streamlit v2 conectada al mart SQLite.

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
    load_mart_tables,
    monthly_attended_vs_billed,
    reconciliation_summary,
    specialty_breakdown,
)
from app.ml_predict import render_prediction_tab
from app.plots import (
    attended_vs_billed_chart,
    reconciliation_donut,
    specialty_bar_chart,
    trend_chart,
)
from app.ui import (
    inject_theme,
    render_gap_card,
    render_header,
    render_kpi_grid,
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


def main() -> None:
    st.set_page_config(
        page_title="Paradigm Live Demo",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    dark_mode = render_theme_toggle()
    inject_theme(dark_mode)

    if not ensure_db(DB_PATH):
        st.stop()

    db_mtime = get_db_mtime(DB_PATH)
    tables = load_mart_tables(str(DB_PATH), db_mtime)

    render_header()
    render_regenerate_section()

    page = st.sidebar.radio(
        "Navegación",
        ["Executive Overview", "Conciliación", "No-Show ML"],
        label_visibility="collapsed",
    )

    if page in ("Executive Overview", "Conciliación"):
        filters = render_sidebar_filters(tables["appointments"])
    else:
        filters = None

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Mart: `{DB_PATH.name}` · {len(tables['appointments'])} citas")

    if page == "Executive Overview":
        render_executive_overview(tables, filters)
    elif page == "Conciliación":
        render_reconciliation(tables, filters)
    else:
        render_prediction_tab(tables, str(DB_PATH), db_mtime)


if __name__ == "__main__":
    main()
