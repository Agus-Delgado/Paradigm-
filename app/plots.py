"""Gráficos Plotly para la Live Demo."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.config import COLOR_ACCENT, COLOR_MUTED, COLOR_PRIMARY, COLOR_SECONDARY


def trend_chart(daily: pd.DataFrame) -> go.Figure:
    """Tendencia temporal: atendidas (barras) + no-show rate (línea, eje secundario)."""
    fig = go.Figure()
    if daily.empty:
        fig.update_layout(
            title="Tendencia temporal — sin datos para el filtro seleccionado",
            height=380,
        )
        return fig

    fig.add_trace(
        go.Bar(
            x=daily["appointment_date"],
            y=daily["attended"],
            name="Atendidas",
            marker_color=COLOR_PRIMARY,
            opacity=0.85,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=daily["appointment_date"],
            y=daily["no_show_rate"] * 100,
            name="No-show rate (%)",
            yaxis="y2",
            mode="lines+markers",
            line=dict(color=COLOR_ACCENT, width=2),
            marker=dict(size=5),
        )
    )
    fig.update_layout(
        title="Tendencia: citas atendidas y tasa de no-show",
        xaxis_title="Fecha de cita",
        yaxis=dict(title="Citas atendidas", gridcolor="rgba(148,163,184,0.2)"),
        yaxis2=dict(
            title="No-show rate (%)",
            overlaying="y",
            side="right",
            range=[0, max(30, daily["no_show_rate"].max() * 110) if daily["no_show_rate"].notna().any() else 30],
            gridcolor="rgba(148,163,184,0.2)",
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400,
        margin=dict(l=40, r=40, t=60, b=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLOR_SECONDARY),
    )
    return fig


def specialty_bar_chart(breakdown: pd.DataFrame) -> go.Figure:
    """Barras horizontales: citas atendidas por especialidad."""
    if breakdown.empty:
        fig = go.Figure()
        fig.update_layout(title="Breakdown por especialidad — sin datos", height=360)
        return fig

    fig = px.bar(
        breakdown,
        x="attended",
        y="specialty_name",
        orientation="h",
        text="attended",
        color="no_show_rate",
        color_continuous_scale=["#99F6E4", COLOR_PRIMARY, COLOR_ACCENT],
        labels={
            "attended": "Citas atendidas",
            "specialty_name": "Especialidad",
            "no_show_rate": "Tasa no-show",
        },
        title="Atendidas por especialidad (color = tasa no-show)",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=max(320, 44 * len(breakdown)),
        coloraxis_colorbar=dict(title="No-show"),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLOR_SECONDARY),
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def reconciliation_donut(summary: pd.DataFrame) -> go.Figure:
    """Distribución de buckets de conciliación (solo atendidas)."""
    if summary.empty:
        fig = go.Figure()
        fig.update_layout(title="Conciliación atención vs facturación — sin datos", height=360)
        return fig

    colors = {
        "ATTENDED_WITH_BILLING": COLOR_PRIMARY,
        "ATTENDED_WITH_PENDING": "#FBBF24",
        "ATTENDED_NO_BILLING": COLOR_ACCENT,
    }
    palette = [colors.get(b, COLOR_MUTED) for b in summary["reconciliation_bucket"]]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=summary["reconciliation_bucket"],
                values=summary["count"],
                hole=0.45,
                marker=dict(colors=palette),
                textinfo="label+value",
            )
        ]
    )
    fig.update_layout(
        title="Distribución de conciliación (citas atendidas)",
        height=380,
        margin=dict(l=20, r=20, t=50, b=20),
        font=dict(color=COLOR_SECONDARY),
    )
    return fig


def attended_vs_billed_chart(monthly: pd.DataFrame) -> go.Figure:
    """Comparativa mensual atención vs facturación."""
    if monthly.empty:
        fig = go.Figure()
        fig.update_layout(title="Atención vs facturación mensual — sin datos", height=380)
        return fig

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=monthly["year_month"],
            y=monthly["attended_count"],
            name="Atendidas",
            marker_color=COLOR_PRIMARY,
            yaxis="y",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=monthly["year_month"],
            y=monthly["billed_amount"],
            name="Facturado (ARS)",
            mode="lines+markers",
            line=dict(color=COLOR_ACCENT, width=2),
            yaxis="y2",
        )
    )
    fig.update_layout(
        title="Atención vs facturación por mes",
        xaxis_title="Mes",
        yaxis=dict(title="Citas atendidas", gridcolor="rgba(148,163,184,0.2)"),
        yaxis2=dict(
            title="Monto facturado (ARS)",
            overlaying="y",
            side="right",
            gridcolor="rgba(148,163,184,0.2)",
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=400,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLOR_SECONDARY),
    )
    return fig
