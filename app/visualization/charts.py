"""Plotly figures for Paradigm dashboards."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Etiquetas en español para ejes (las claves internas siguen en inglés).
_LOGICAL_TYPE_AXIS_ES: dict[str, str] = {
    "numeric": "Numérico",
    "categorical": "Categórico",
    "boolean": "Booleano",
    "datetime": "Fecha / hora",
    "text": "Texto",
    "id": "Identificador",
}


def _layout_base(fig: go.Figure) -> go.Figure:
    """Plantilla clara y consistente; los márgenes específicos de cada gráfico se respetan."""
    fig.update_layout(template="plotly_white")
    return fig


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
    return _layout_base(fig)


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
    return _layout_base(fig)


def chart_first_numeric_histogram(series: pd.Series, title: str) -> go.Figure:
    num = pd.to_numeric(series, errors="coerce").dropna()
    if num.empty:
        return _empty_figure("Sin valores numéricos para graficar.")
    fig = px.histogram(num, nbins=min(40, max(10, len(num) // 5)), title=title)
    fig.update_layout(showlegend=False)
    return _layout_base(fig)


def chart_logical_type_distribution(counts: dict[str, int]) -> go.Figure:
    """Barras horizontales: cantidad de columnas por tipo inferido."""
    if not counts:
        return _empty_figure("No hay tipos para graficar.")
    sorted_items = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    labels = [_LOGICAL_TYPE_AXIS_ES.get(k, k) for k, _ in sorted_items]
    values = [v for _, v in sorted_items]
    fig = px.bar(
        x=values,
        y=labels,
        orientation="h",
        labels={"x": "Columnas", "y": "Tipo inferido"},
        title="Columnas por tipo inferido",
    )
    fig.update_layout(showlegend=False, margin=dict(l=80))
    return _layout_base(fig)


def chart_categorical_top(series: pd.Series, title: str, top_n: int = 15) -> go.Figure:
    vc = series.astype(str).value_counts().head(top_n)
    if vc.empty:
        return _empty_figure("Sin datos para graficar.")
    fig = px.bar(x=vc.index.astype(str), y=vc.values, labels={"x": "Categoría", "y": "Frecuencia"}, title=title)
    fig.update_layout(xaxis_tickangle=-45, showlegend=False, margin=dict(b=120))
    return _layout_base(fig)


def chart_numeric_boxplot(series: pd.Series, title: str) -> go.Figure:
    num = pd.to_numeric(series, errors="coerce").dropna()
    if num.empty:
        return _empty_figure("Sin valores numéricos para graficar.")
    fig = go.Figure(data=[go.Box(y=num, name="", boxpoints="outliers")])
    fig.update_layout(title=title, showlegend=False, yaxis_title="Valor")
    return _layout_base(fig)


def chart_boolean_counts(series: pd.Series, title: str) -> go.Figure:
    vc = series.astype(str).str.strip().str.lower().value_counts()
    if vc.empty:
        return _empty_figure("Sin datos para graficar.")
    fig = px.bar(
        x=vc.index.astype(str),
        y=vc.values,
        labels={"x": "Valor", "y": "Frecuencia"},
        title=title,
    )
    fig.update_layout(xaxis_tickangle=0, showlegend=False)
    return _layout_base(fig)


def chart_datetime_temporal(series: pd.Series, title: str) -> go.Figure:
    dt = pd.to_datetime(series, errors="coerce").dropna()
    if dt.empty:
        return _empty_figure("Sin fechas válidas para graficar.")
    fig = px.histogram(dt, nbins=min(60, max(10, len(dt) // 3)), title=title)
    fig.update_layout(showlegend=False, xaxis_title="Fecha / tiempo", yaxis_title="Frecuencia")
    return _layout_base(fig)


def build_exploration_chart(
    series: pd.Series,
    logical_type: str,
    chart_kind: str,
    title: str,
) -> go.Figure:
    """Gráfico exploratorio según tipo inferido y tipo elegido (sin combinaciones inválidas)."""
    if series.empty:
        return _empty_figure("Sin datos en la vista filtrada para esta columna.")
    if logical_type in ("text", "id"):
        return _empty_figure("Este tipo de columna no se recomienda para gráficos; elegí otra columna.")
    if chart_kind == "ninguno":
        return _empty_figure("No hay visualización para esta combinación.")

    if logical_type == "numeric":
        if chart_kind == "histograma":
            return chart_first_numeric_histogram(series, title)
        if chart_kind == "boxplot":
            return chart_numeric_boxplot(series, title)
        return chart_first_numeric_histogram(series, title)

    if logical_type == "categorical":
        return chart_categorical_top(series, title)

    if logical_type == "boolean":
        return chart_boolean_counts(series, title)

    if logical_type == "datetime":
        if chart_kind == "temporal":
            return chart_datetime_temporal(series, title)
        return chart_datetime_temporal(series, title)

    return _empty_figure("Tipo de columna no soportado para exploración.")
