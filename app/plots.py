"""Gráficos Plotly para la Live Demo — tema dark premium."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.config import COLOR_ACCENT, COLOR_CHART, COLOR_MUTED, COLOR_TEXT, COLOR_WARNING

# Shared dark layout applied to every figure
_DARK_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, Segoe UI, sans-serif", color=COLOR_TEXT),
    margin=dict(l=40, r=40, t=60, b=40),
)


def _dark_layout(**overrides) -> dict:
    """Merge overrides into _DARK_LAYOUT; margin dicts are combined, not replaced twice."""
    layout = dict(_DARK_LAYOUT)
    margin_extra = overrides.pop("margin", None)
    layout.update(overrides)
    if margin_extra is not None:
        layout["margin"] = {**_DARK_LAYOUT["margin"], **margin_extra}
    return layout


# Color scale: navy → cyan
_SCALE_CYAN = ["#1e3a8a", COLOR_CHART]


def trend_chart(daily: pd.DataFrame) -> go.Figure:
    """Tendencia temporal: atendidas (barras) + no-show rate (línea, eje secundario)."""
    fig = go.Figure()
    if daily.empty:
        fig.update_layout(
            title="Tendencia temporal — sin datos para el filtro seleccionado",
            height=380,
            **_DARK_LAYOUT,
        )
        return fig

    fig.add_trace(
        go.Bar(
            x=daily["appointment_date"],
            y=daily["attended"],
            name="Atendidas",
            marker_color=COLOR_CHART,
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
        **_DARK_LAYOUT,
        title="Tendencia: citas atendidas y tasa de no-show",
        xaxis_title="Fecha de cita",
        yaxis=dict(
            title="Citas atendidas",
            gridcolor="rgba(0,245,255,0.08)",
        ),
        yaxis2=dict(
            title="No-show rate (%)",
            overlaying="y",
            side="right",
            range=[
                0,
                max(30, daily["no_show_rate"].max() * 110)
                if daily["no_show_rate"].notna().any()
                else 30,
            ],
            gridcolor="rgba(0,245,255,0.08)",
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400,
    )
    return fig


def specialty_bar_chart(breakdown: pd.DataFrame) -> go.Figure:
    """Barras horizontales: citas atendidas por especialidad."""
    if breakdown.empty:
        fig = go.Figure()
        fig.update_layout(title="Breakdown por especialidad — sin datos", height=360, **_DARK_LAYOUT)
        return fig

    fig = px.bar(
        breakdown,
        x="attended",
        y="specialty_name",
        orientation="h",
        text="attended",
        color="no_show_rate",
        color_continuous_scale=_SCALE_CYAN,
        labels={
            "attended":      "Citas atendidas",
            "specialty_name": "Especialidad",
            "no_show_rate":  "Tasa no-show",
        },
        title="Atendidas por especialidad (color = tasa no-show)",
        template="plotly_dark",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        **_DARK_LAYOUT,
        height=max(320, 44 * len(breakdown)),
        coloraxis_colorbar=dict(title="No-show"),
    )
    return fig


def reconciliation_donut(summary: pd.DataFrame) -> go.Figure:
    """Distribución de buckets de conciliación (solo atendidas)."""
    if summary.empty:
        fig = go.Figure()
        fig.update_layout(
            title="Conciliación atención vs facturación — sin datos",
            height=360,
            **_DARK_LAYOUT,
        )
        return fig

    colors = {
        "ATTENDED_WITH_BILLING": COLOR_CHART,
        "ATTENDED_WITH_PENDING": COLOR_WARNING,
        "ATTENDED_NO_BILLING":   COLOR_ACCENT,
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
        **_DARK_LAYOUT,
        title="Distribución de conciliación (citas atendidas)",
        height=380,
    )
    return fig


def attended_vs_billed_chart(monthly: pd.DataFrame) -> go.Figure:
    """Comparativa mensual atención vs facturación."""
    if monthly.empty:
        fig = go.Figure()
        fig.update_layout(
            title="Atención vs facturación mensual — sin datos",
            height=380,
            **_DARK_LAYOUT,
        )
        return fig

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=monthly["year_month"],
            y=monthly["attended_count"],
            name="Atendidas",
            marker_color=COLOR_CHART,
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
        **_DARK_LAYOUT,
        title="Atención vs facturación por mes",
        xaxis_title="Mes",
        yaxis=dict(title="Citas atendidas",       gridcolor="rgba(0,245,255,0.08)"),
        yaxis2=dict(
            title="Monto facturado (ARS)",
            overlaying="y",
            side="right",
            gridcolor="rgba(0,245,255,0.08)",
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=400,
    )
    return fig


def shap_global_importance_chart(
    importance: list[dict],
    title: str = "Importancia global (SHAP)",
) -> go.Figure:
    """Barras horizontales: mean |SHAP| por feature."""
    if not importance:
        fig = go.Figure()
        fig.update_layout(title=f"{title} — sin datos", height=360, **_DARK_LAYOUT)
        return fig

    df = pd.DataFrame(importance)
    value_col = "mean_abs_shap" if "mean_abs_shap" in df.columns else "importance"
    df = df.sort_values(value_col, ascending=True).tail(15)

    fig = px.bar(
        df,
        x=value_col,
        y="feature",
        orientation="h",
        title=title,
        labels={value_col: "Impacto medio |SHAP|", "feature": "Feature"},
        color=value_col,
        color_continuous_scale=_SCALE_CYAN,
        template="plotly_dark",
    )
    fig.update_layout(
        **_DARK_LAYOUT,
        height=max(360, 28 * len(df)),
        showlegend=False,
        coloraxis_showscale=False,
    )
    return fig


def shap_local_waterfall_chart(
    feature_names: list[str],
    shap_row: list[float],
    expected_value: float,
    title: str = "Explicación local (contribuciones SHAP)",
) -> go.Figure:
    """Waterfall en Plotly: valor base + contribuciones SHAP."""
    pairs = sorted(zip(feature_names, shap_row), key=lambda x: abs(x[1]), reverse=True)[:12]
    labels = ["Base E[f(x)]"] + [p[0] for p in pairs] + ["Total"]
    contributions = [p[1] for p in pairs]
    total = expected_value + sum(contributions)

    fig = go.Figure(
        go.Waterfall(
            name="SHAP",
            orientation="v",
            measure=["absolute"] + ["relative"] * len(pairs) + ["total"],
            x=labels,
            y=[expected_value] + contributions + [total],
            connector=dict(line=dict(color=COLOR_MUTED, width=1, dash="dot")),
            increasing=dict(marker=dict(color=COLOR_ACCENT)),
            decreasing=dict(marker=dict(color=COLOR_CHART)),
            totals=dict(marker=dict(color="#38bdf8")),
        )
    )
    fig.update_layout(
        **_dark_layout(margin={"b": 120}),
        title=title,
        height=420,
        xaxis_tickangle=-35,
    )
    return fig


def shap_force_bar_chart(
    feature_names: list[str],
    shap_row: list[float],
    title: str = "Force plot (contribuciones SHAP)",
) -> go.Figure:
    """Barras divergentes: contribución positiva/negativa por feature."""
    pairs = sorted(zip(feature_names, shap_row), key=lambda x: abs(x[1]), reverse=True)[:12]
    pairs = sorted(pairs, key=lambda x: x[1])
    colors = [COLOR_ACCENT if v >= 0 else COLOR_CHART for _, v in pairs]

    fig = go.Figure(
        go.Bar(
            x=[v for _, v in pairs],
            y=[f for f, _ in pairs],
            orientation="h",
            marker_color=colors,
        )
    )
    fig.update_layout(
        **_DARK_LAYOUT,
        title=title,
        xaxis_title="Contribución SHAP",
        height=max(320, 30 * len(pairs)),
    )
    return fig


def business_impact_chart(comparison_df: pd.DataFrame, top_pct: int) -> go.Figure:
    """Comparación baseline vs priorizado (ARS)."""
    if comparison_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Impacto de negocio — sin datos", height=360, **_DARK_LAYOUT)
        return fig

    fig = px.bar(
        comparison_df,
        x="metric",
        y="value_ars",
        color="scenario",
        barmode="group",
        text="value_ars",
        labels={"value_ars": "ARS", "metric": "Métrica", "scenario": "Escenario"},
        title=f"Baseline vs top {top_pct}% priorizado",
        color_discrete_sequence=[COLOR_MUTED, COLOR_CHART],
        template="plotly_dark",
    )
    fig.update_traces(texttemplate="%{y:,.0f}", textposition="outside")
    fig.update_layout(**_DARK_LAYOUT, height=400)
    return fig
