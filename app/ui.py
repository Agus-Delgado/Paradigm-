"""Componentes UI: tema, KPI cards responsivas, sidebar y estados vacíos."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from app.config import (
    COLOR_ACCENT,
    COLOR_BG_DARK,
    COLOR_BG_LIGHT,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    SYNTHETIC_BANNER,
)
from app.data import ExecutiveKpis, FilterState, run_regenerate_pipeline


def inject_theme(dark_mode: bool) -> None:
    """CSS global: paleta médica y KPI cards responsivas (3 por fila en mobile)."""
    bg = COLOR_BG_DARK if dark_mode else COLOR_BG_LIGHT
    fg = "#E2E8F0" if dark_mode else COLOR_SECONDARY
    card_bg = "#1E293B" if dark_mode else "#FFFFFF"
    border = "#334155" if dark_mode else "#E2E8F0"

    st.markdown(
        f"""
        <style>
        .paradigm-header {{
            margin-bottom: 0.25rem;
        }}
        .paradigm-subtitle {{
            color: {COLOR_MUTED};
            font-size: 0.95rem;
            margin-bottom: 1rem;
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.75rem;
            margin-bottom: 0.75rem;
        }}
        @media (max-width: 900px) {{
            .kpi-grid {{
                grid-template-columns: repeat(3, 1fr);
            }}
        }}
        @media (max-width: 640px) {{
            .kpi-grid {{
                grid-template-columns: repeat(3, 1fr);
                gap: 0.5rem;
            }}
            .kpi-value {{
                font-size: 1.15rem;
            }}
            .kpi-label {{
                font-size: 0.68rem;
            }}
        }}
        .kpi-card {{
            background: {card_bg};
            border: 1px solid {border};
            border-radius: 10px;
            padding: 0.85rem 1rem;
            min-height: 88px;
        }}
        .kpi-label {{
            color: {COLOR_MUTED};
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 0.25rem;
        }}
        .kpi-value {{
            color: {fg};
            font-size: 1.55rem;
            font-weight: 700;
            line-height: 1.2;
        }}
        .kpi-delta {{
            color: {COLOR_MUTED};
            font-size: 0.8rem;
            margin-top: 0.15rem;
        }}
        .gap-highlight {{
            background: linear-gradient(135deg, {COLOR_ACCENT}22, {card_bg});
            border: 1px solid {COLOR_ACCENT}55;
            border-radius: 12px;
            padding: 1rem 1.25rem;
            margin: 1rem 0;
        }}
        .stApp {{
            background-color: {bg};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        '<p class="paradigm-header"><span style="font-size:1.75rem;font-weight:700;">'
        f'<span style="color:{COLOR_PRIMARY};">Paradigm</span> Live Demo</span></p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="paradigm-subtitle">Analytics engineering · operaciones ambulatorias · mart SQLite</p>',
        unsafe_allow_html=True,
    )
    st.info(SYNTHETIC_BANNER)


def _kpi_card_html(label: str, value: str, delta: str = "") -> str:
    delta_html = f'<div class="kpi-delta">{delta}</div>' if delta else ""
    return (
        f'<div class="kpi-card"><div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>{delta_html}</div>'
    )


def render_kpi_grid(kpis: ExecutiveKpis) -> None:
    """6 KPI cards en 2 filas × 3 columnas (grid CSS responsivo)."""
    ns_pct = f"{kpis.no_show_rate * 100:.1f}%" if kpis.no_show_rate is not None else "n/a"
    can_pct = (
        f"{kpis.cancellation_rate * 100:.1f}%"
        if kpis.cancellation_rate is not None
        else "n/a"
    )
    revenue_fmt = f"${kpis.revenue:,.0f}"

    row1 = [
        _kpi_card_html("Citas total", f"{kpis.citas_total:,}"),
        _kpi_card_html("Atendidas", f"{kpis.attended:,}"),
        _kpi_card_html("No-show rate", ns_pct, delta=f"{kpis.noshow} no-shows"),
    ]
    row2 = [
        _kpi_card_html("Tasa cancelación", can_pct, delta=f"{kpis.cancelled} canceladas"),
        _kpi_card_html("Ingreso facturado", revenue_fmt, delta="ARS · no VOID"),
        _kpi_card_html(
            "Brechas",
            f"{kpis.billing_gap_count}",
            delta="ATTENDED_NO_BILLING",
        ),
    ]
    st.markdown(f'<div class="kpi-grid">{"".join(row1)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-grid">{"".join(row2)}</div>', unsafe_allow_html=True)


def render_gap_card(kpis: ExecutiveKpis) -> None:
    st.markdown(
        f"""
        <div class="gap-highlight">
            <strong style="color:{COLOR_ACCENT};">Brecha de facturación</strong><br/>
            <span style="font-size:1.25rem;font-weight:600;">
                {kpis.billing_gap_count} citas atendidas sin línea de facturación
            </span><br/>
            <span style="color:{COLOR_MUTED};">
                Monto reconocido en puente: ${kpis.billing_gap_amount:,.0f} ARS ·
                Revisá la pestaña Conciliación para el detalle.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_filters(appointments: pd.DataFrame) -> FilterState:
    """Filtros compartidos para Overview y Conciliación."""
    st.sidebar.markdown("### Filtros")
    min_d = appointments["appointment_date"].min().date()
    max_d = appointments["appointment_date"].max().date()

    date_range = st.sidebar.date_input(
        "Rango de fechas (cita)",
        value=(min_d, max_d),
        min_value=min_d,
        max_value=max_d,
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        date_start, date_end = date_range
    else:
        date_start = date_end = date_range if isinstance(date_range, date) else min_d

    specialties = st.sidebar.multiselect(
        "Especialidad",
        options=sorted(appointments["specialty_name"].dropna().unique()),
    )
    providers = st.sidebar.multiselect(
        "Proveedor",
        options=sorted(appointments["provider_label"].dropna().unique()),
    )
    channels = st.sidebar.multiselect(
        "Canal",
        options=sorted(appointments["channel_code"].dropna().unique()),
    )

    return FilterState(
        date_start=pd.Timestamp(date_start),
        date_end=pd.Timestamp(date_end),
        specialties=specialties,
        providers=providers,
        channels=channels,
    )


def render_regenerate_section() -> None:
    """Botón regenerar con confirmación fuerte (warning + checkbox)."""
    with st.sidebar.expander("Regenerar datos", expanded=False):
        st.warning(
            "Esta acción **sobrescribe** los CSV sintéticos y reconstruye "
            "`paradigm_mart.db`. Puede tardar varios segundos."
        )
        confirm = st.checkbox(
            "Entiendo y quiero regenerar los datos sintéticos",
            key="regen_confirm",
        )
        include_train = st.checkbox(
            "También re-entrenar modelo no-show",
            value=False,
            key="regen_train",
        )
        if st.button("Ejecutar regeneración", type="primary", disabled=not confirm):
            with st.spinner("Ejecutando pipeline…"):
                ok, log = run_regenerate_pipeline(include_train=include_train)
            with st.expander("Log de ejecución", expanded=not ok):
                st.code(log or "(sin salida)")
            if ok:
                st.cache_data.clear()
                st.success("Datos regenerados. Recargando…")
                st.rerun()
            else:
                st.error("Falló la regeneración. Revisá el log.")


def render_theme_toggle() -> bool:
    st.sidebar.markdown("---")
    return st.sidebar.toggle("Modo oscuro", value=False, key="dark_mode")
