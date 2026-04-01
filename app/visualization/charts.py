"""Plotly figures for Paradigm dashboards."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
    )
    fig.update_xaxis(visible=False)
    fig.update_yaxis(visible=False)
    return fig


def chart_nulls_by_column(column_names: list[str], null_pcts: list[float]) -> go.Figure:
    if not column_names or not null_pcts:
        return _empty_figure("No hay columnas para graficar nulos.")
    if len(column_names) != len(null_pcts):
        return _empty_figure("Datos incompletos para el gráfico de nulos.")
    fig = px.bar(
        x=list(column_names),
        y=null_pcts,
        labels={"x": "Columna", "y": "% nulos"},
        title="Nulos por columna (%)",
    )
    fig.update_layout(xaxis_tickangle=-45, showlegend=False, margin=dict(b=120))
    return fig


def chart_first_numeric_histogram(series: pd.Series, title: str) -> go.Figure:
    num = pd.to_numeric(series, errors="coerce").dropna()
    if num.empty:
        return _empty_figure("Sin valores numéricos para graficar.")
    fig = px.histogram(num, nbins=min(40, max(10, len(num) // 5)), title=title)
    fig.update_layout(showlegend=False)
    return fig


def chart_categorical_top(series: pd.Series, title: str, top_n: int = 15) -> go.Figure:
    vc = series.astype(str).value_counts().head(top_n)
    if vc.empty:
        return _empty_figure("Sin datos para graficar.")
    fig = px.bar(x=vc.index.astype(str), y=vc.values, labels={"x": "Categoría", "y": "Frecuencia"}, title=title)
    fig.update_layout(xaxis_tickangle=-45, showlegend=False, margin=dict(b=120))
    return fig
