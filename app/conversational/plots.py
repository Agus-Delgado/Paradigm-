"""Gráficos Plotly contextuales con estilo premium."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.config import COLOR_ACCENT, COLOR_MUTED, COLOR_PRIMARY, COLOR_TEXT
from app.conversational.legacy_bridge import insights_pick_compare_pair
from app.conversational.types import AnalysisPlan, Domain

_LAYOUT = dict(
    template="plotly_dark",
    font=dict(family="Inter, Segoe UI, sans-serif", color=COLOR_TEXT),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=48, r=32, t=56, b=48),
    height=420,
)


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=14, color=COLOR_MUTED),
    )
    fig.update_layout(**_LAYOUT, xaxis_visible=False, yaxis_visible=False)
    return fig


def _apply_layout(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(**_LAYOUT, title=dict(text=title, x=0, xanchor="left", font=dict(size=16)))
    return fig


def _clinic_estado_chart(df: pd.DataFrame) -> go.Figure | None:
    if "estado_turno" not in df.columns:
        return None
    est = df["estado_turno"].astype(str).str.strip().str.lower()
    vc = est.value_counts().reset_index()
    vc.columns = ["estado", "count"]
    if vc.empty:
        return None
    colors = [COLOR_PRIMARY, COLOR_ACCENT, "#6366F1", "#94A3B8"]
    fig = px.pie(
        vc,
        names="estado",
        values="count",
        color_discrete_sequence=colors,
        hole=0.42,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return _apply_layout(fig, "Distribución de estados de turno")


def _mart_status_chart(df: pd.DataFrame) -> go.Figure | None:
    if "status_code" not in df.columns:
        return None
    vc = df["status_code"].value_counts().reset_index()
    vc.columns = ["status", "count"]
    fig = px.bar(
        vc,
        x="status",
        y="count",
        color="status",
        color_discrete_sequence=[COLOR_PRIMARY, COLOR_ACCENT, "#6366F1", "#94A3B8"],
    )
    fig.update_layout(showlegend=False)
    return _apply_layout(fig, "Citas por estado operativo")


def _segment_metric_chart(
    df: pd.DataFrame,
    segment_col: str,
    metric_col: str,
    title: str,
) -> go.Figure | None:
    if segment_col not in df.columns or metric_col not in df.columns:
        return None
    sub = df[[segment_col, metric_col]].copy()
    sub[metric_col] = pd.to_numeric(sub[metric_col], errors="coerce")
    sub["_segment"] = sub[segment_col].astype(str)
    sub = sub.dropna(subset=[metric_col])
    if sub.empty:
        return None
    agg = (
        sub.groupby("_segment", as_index=False)[metric_col]
        .mean()
        .sort_values(metric_col, ascending=True)
        .tail(12)
    )
    fig = px.bar(
        agg,
        x=metric_col,
        y="_segment",
        orientation="h",
        color=metric_col,
        color_continuous_scale=[COLOR_MUTED, COLOR_PRIMARY],
    )
    fig.update_layout(coloraxis_showscale=False, showlegend=False)
    return _apply_layout(fig, title)


def _mart_noshow_by_segment(df: pd.DataFrame, segment_col: str) -> go.Figure | None:
    if segment_col not in df.columns or "status_code" not in df.columns:
        return None
    sub = df[[segment_col, "status_code"]].copy()
    rows: list[dict] = []
    for seg, grp in sub.groupby(segment_col):
        attended = int((grp["status_code"] == "ATTENDED").sum())
        noshow = int((grp["status_code"] == "NO_SHOW").sum())
        denom = attended + noshow
        if denom < 5:
            continue
        rows.append(
            {
                "segment": str(seg),
                "no_show_rate": noshow / denom * 100.0,
                "citas": denom,
            }
        )
    if not rows:
        return None
    agg = pd.DataFrame(rows).sort_values("no_show_rate", ascending=True).tail(12)
    fig = px.bar(
        agg,
        x="no_show_rate",
        y="segment",
        orientation="h",
        color="no_show_rate",
        color_continuous_scale=[COLOR_PRIMARY, COLOR_ACCENT],
        hover_data=["citas"],
    )
    fig.update_layout(coloraxis_showscale=False, xaxis_title="No-show rate (%)", yaxis_title="")
    return _apply_layout(fig, f"No-show rate por {segment_col}")


def _time_series_chart(
    df: pd.DataFrame,
    date_col: str,
    value_col: str | None,
    title: str,
) -> go.Figure | None:
    if date_col not in df.columns:
        return None
    sub = df.copy()
    sub[date_col] = pd.to_datetime(sub[date_col], errors="coerce")
    sub = sub.dropna(subset=[date_col])
    if sub.empty:
        return None

    if value_col and value_col in sub.columns:
        sub[value_col] = pd.to_numeric(sub[value_col], errors="coerce")
        sub["_date"] = sub[date_col].dt.date
        agg = sub.groupby("_date", as_index=False)[value_col].sum()
        fig = px.area(
            agg,
            x="_date",
            y=value_col,
            line_shape="spline",
            color_discrete_sequence=[COLOR_PRIMARY],
        )
    else:
        sub["_date"] = sub[date_col].dt.date
        agg = sub.groupby("_date", as_index=False).size()
        agg.columns = ["_date", "count"]
        fig = px.line(
            agg,
            x="_date",
            y="count",
            markers=True,
            color_discrete_sequence=[COLOR_PRIMARY],
        )
    return _apply_layout(fig, title)


def _distribution_chart(df: pd.DataFrame, col: str, title: str) -> go.Figure | None:
    if col not in df.columns:
        return None
    num = pd.to_numeric(df[col], errors="coerce").dropna()
    if num.empty:
        return None
    fig = px.histogram(
        num,
        nbins=min(40, max(12, len(num) // 20)),
        color_discrete_sequence=[COLOR_PRIMARY],
        opacity=0.85,
    )
    fig.update_layout(bargap=0.05, xaxis_title=col, yaxis_title="Frecuencia")
    return _apply_layout(fig, title)


def _boxplot_outliers(df: pd.DataFrame, col: str, title: str) -> go.Figure | None:
    if col not in df.columns:
        return None
    num = pd.to_numeric(df[col], errors="coerce").dropna()
    if len(num) < 4:
        return None
    fig = px.box(num, color_discrete_sequence=[COLOR_ACCENT], points="outliers")
    fig.update_layout(showlegend=False, xaxis_visible=False)
    return _apply_layout(fig, title)


def _find_datetime_col(logical_types: dict[str, str]) -> str | None:
    for col, lt in logical_types.items():
        if lt == "datetime":
            return col
    for candidate in ("appointment_date", "fecha_turno", "fecha", "date"):
        if candidate in logical_types:
            return candidate
    return None


def build_contextual_plots(
    df: pd.DataFrame,
    logical_types: dict[str, str],
    plan: AnalysisPlan,
) -> list[tuple[str, go.Figure]]:
    """Genera 2–4 gráficos Plotly alineados al plan de análisis."""
    figures: list[tuple[str, go.Figure]] = []
    domain: Domain = plan.domain

    if domain == "healthcare_clinic":
        fig = _clinic_estado_chart(df)
        if fig is not None:
            figures.append(("estado", fig))
        segment = plan.segment_col or "especialidad"
        if segment in df.columns and "ingreso_neto" in df.columns:
            fig = _segment_metric_chart(
                df, segment, "ingreso_neto", f"Ingreso neto medio por {segment}"
            )
            if fig is not None:
                figures.append(("ingreso_segment", fig))
        elif segment in df.columns:
            vc = df[segment].astype(str).value_counts().head(10).reset_index()
            vc.columns = [segment, "count"]
            fig = px.bar(vc, x=segment, y="count", color_discrete_sequence=[COLOR_PRIMARY])
            fig.update_layout(xaxis_tickangle=-35)
            figures.append(("volume", _apply_layout(fig, f"Volumen por {segment}")))
        date_col = _find_datetime_col(logical_types)
        if date_col:
            fig = _time_series_chart(df, date_col, "ingreso_neto" if "ingreso_neto" in df.columns else None, "Tendencia temporal")
            if fig is not None:
                figures.append(("trend", fig))

    elif domain == "healthcare_mart":
        fig = _mart_status_chart(df)
        if fig is not None:
            figures.append(("status", fig))
        segment = plan.segment_col or "specialty_name"
        fig = _mart_noshow_by_segment(df, segment)
        if fig is not None:
            figures.append(("noshow_segment", fig))
        date_col = _find_datetime_col(logical_types) or "appointment_date"
        fig = _time_series_chart(df, date_col, None, "Volumen de citas en el tiempo")
        if fig is not None:
            figures.append(("trend", fig))

    elif domain == "finance":
        metric = plan.metric_col
        if metric and metric in df.columns:
            figures.append(("dist", _distribution_chart(df, metric, f"Distribución de {metric}") or _empty_figure("Sin datos")))
            figures.append(("box", _boxplot_outliers(df, metric, f"Outliers — {metric}") or _empty_figure("Sin datos")))
        segment = plan.segment_col
        if segment and metric and segment in df.columns:
            fig = _segment_metric_chart(df, segment, metric, f"{metric} por {segment}")
            if fig is not None:
                figures.append(("segment", fig))

    elif domain == "operations":
        metric = plan.metric_col or "defectos"
        segment = plan.segment_col or "planta"
        if metric in df.columns:
            figures.append(
                ("dist", _distribution_chart(df, metric, f"Distribución de {metric}") or _empty_figure("Sin datos"))
            )
        if segment in df.columns and metric in df.columns:
            fig = _segment_metric_chart(df, segment, metric, f"{metric} por {segment}")
            if fig is not None:
                figures.append(("segment", fig))
        if "tiempo_ciclo_min" in df.columns and "turno" in df.columns:
            sub = df.groupby("turno", as_index=False)["tiempo_ciclo_min"].mean()
            fig = px.bar(
                sub,
                x="turno",
                y="tiempo_ciclo_min",
                color="turno",
                color_discrete_sequence=[COLOR_PRIMARY, COLOR_ACCENT, "#6366F1"],
            )
            fig.update_layout(showlegend=False)
            figures.append(("ciclo_turno", _apply_layout(fig, "Tiempo de ciclo por turno")))
        date_col = _find_datetime_col(logical_types) or "fecha"
        if date_col in df.columns and metric in df.columns:
            fig = _time_series_chart(df, date_col, metric, f"Tendencia de {metric}")
            if fig is not None:
                figures.append(("trend", fig))

    else:
        pair = insights_pick_compare_pair(df, logical_types)
        metric = plan.metric_col
        segment = plan.segment_col
        if pair and not metric:
            segment, metric = pair
        if metric and metric in df.columns:
            figures.append(("dist", _distribution_chart(df, metric, f"Distribución de {metric}") or _empty_figure("Sin datos")))
        if segment and metric and segment in df.columns:
            fig = _segment_metric_chart(df, segment, metric, f"Comparación {metric} × {segment}")
            if fig is not None:
                figures.append(("compare", fig))
        date_col = _find_datetime_col(logical_types)
        if date_col and metric:
            fig = _time_series_chart(df, date_col, metric, f"Tendencia de {metric}")
            if fig is not None:
                figures.append(("trend", fig))

    if len(figures) < 2:
        nums = [c for c, t in logical_types.items() if t == "numeric"]
        if nums:
            col = nums[0]
            fig = _distribution_chart(df, col, f"Distribución de {col}")
            if fig is not None:
                figures.append(("fallback_dist", fig))

    return figures[:4]
