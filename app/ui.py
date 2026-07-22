"""Componentes UI: tema premium dark, KPI cards, landing page y wizard."""

from __future__ import annotations

import base64
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from app.config import (
    APP_VERSION,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_PRIMARY_SOFT,
    COLOR_TEXT,
    LAST_UPDATE,
    REPO_ROOT,
    SYNTHETIC_BANNER,
)
from app.export_report import build_analysis_report_md
from app.data import ExecutiveKpis, FilterState, run_regenerate_pipeline

_CSS_PATH = REPO_ROOT / "assets" / "css" / "custom.css"
_LANDING_DIR = REPO_ROOT / "assets" / "landing"


# ── Helpers ────────────────────────────────────────────────────────────────

def _load_css() -> str:
    """Read custom.css; return empty string if file is missing."""
    try:
        return _CSS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _img_b64(name: str) -> tuple[str, str]:
    """Return (base64_data, mime_type) for a landing image.
    Tries .webp first, then .jpg, then .png."""
    for ext, mime in [(".webp", "image/webp"), (".jpg", "image/jpeg"), (".png", "image/png")]:
        p = _LANDING_DIR / f"{name}{ext}"
        if p.exists():
            return base64.b64encode(p.read_bytes()).decode(), mime
    return "", "image/webp"


# ── Theme injection ─────────────────────────────────────────────────────────

def inject_theme(dark_mode: bool = True) -> None:  # noqa: ARG001  (always dark)
    """Inject the full premium dark CSS into Streamlit."""
    css = _load_css()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def render_theme_toggle() -> bool:
    """Theme is always dark — returns True without rendering any UI widget."""
    return True


# ── App header ──────────────────────────────────────────────────────────────

def render_header() -> None:
    st.markdown(
        f"""
        <div class="paradigm-header">
          <span style="font-size:1.8rem;font-weight:800;color:{COLOR_PRIMARY_SOFT};
                       letter-spacing:-0.02em;">Paradigm</span>
          <span style="font-size:1.8rem;font-weight:400;color:{COLOR_TEXT};
                       letter-spacing:-0.02em;"> Decision Lab</span>
          <span style="font-size:0.75rem;font-weight:500;color:{COLOR_MUTED};
                       margin-left:0.6rem;vertical-align:middle;">v{APP_VERSION}</span>
        </div>
        <p class="paradigm-subtitle">
          Decision Intelligence Laboratory · Observe → Decide · actualizado {LAST_UPDATE}
        </p>
        """,
        unsafe_allow_html=True,
    )
    st.info(SYNTHETIC_BANNER)


def render_workspace_header(title: str, meta: str) -> None:
    """Cabecera consistente para pestañas del workspace analítico."""
    st.markdown(
        f'<div class="explorer-nav-card">'
        f'<span class="explorer-nav-label">{title}</span>'
        f'<span class="explorer-nav-meta">{meta}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def render_app_footer() -> None:
    """Footer con versión y disclaimer."""
    st.markdown(
        f"""
        <div class="paradigm-footer">
          <strong>Paradigm</strong> v{APP_VERSION} · última actualización {LAST_UPDATE}<br/>
          Decision Intelligence Laboratory · datos sintéticos · portfolio
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Landing page ─────────────────────────────────────────────────────────────

def render_landing_page() -> None:
    """Full-screen hero landing. Sets show_landing=False when user clicks Enter."""
    inject_theme()

    # Hero ─────────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div class="paradigm-landing-hero"
             style="text-align:center;width:100%;display:flex;flex-direction:column;align-items:center;">
          <div class="hero-badge" style="text-align:center;">DECISION INTELLIGENCE LABORATORY</div>
          <h1 class="hero-title" style="text-align:center;width:100%;margin-left:auto;margin-right:auto;">
            Paradigm
          </h1>
          <p class="hero-subtitle" style="text-align:center;width:100%;">
            De la evidencia a la decisión operativa
          </p>
          <p class="hero-description"
             style="text-align:center;max-width:680px;margin:0 auto 0.7rem;">
            Observá el mart, predicí riesgo, explicá con evidencia y decidí a quién priorizar —
            sin inventar causalidad.
          </p>
          <p class="hero-description-small"
             style="text-align:center;max-width:560px;margin:0 auto 2.5rem;">
            Laboratorio reproducible sobre operaciones ambulatorias sintéticas:
            Observe → Predict → Explain → Decide → Learn.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Feature cards ────────────────────────────────────────────────────────
    st.markdown(
        """
        <div class="feature-grid">
          <div class="feature-card">
            <div class="feature-icon">01</div>
            <div class="feature-card-title">Cómo funciona</div>
            <div class="feature-card-body">
              Mart gobernado → predicción y explicación → motor Decide
              (riesgo, uplift, capacidad) → chat y BI que consumen los mismos
              artefactos auditables.
            </div>
          </div>
          <div class="feature-card">
            <div class="feature-icon">02</div>
            <div class="feature-card-title">Objetivo</div>
            <div class="feature-card-body">
              Convertir evidencia en opciones de decisión comparables:
              a quién contactar, bajo qué política, con qué incertidumbre —
              sin automatizar campañas reales.
            </div>
          </div>
          <div class="feature-card">
            <div class="feature-icon">03</div>
            <div class="feature-card-title">Valor diferencial</div>
            <div class="feature-card-body">
              Metodología honesta: dato, predicción, simulación y recomendación
              etiquetados. Asociación ≠ causalidad. Listo para portfolio y demo.
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Image cards ──────────────────────────────────────────────────────────
    st.markdown(
        '<p class="landing-section-title">Capacidades <span>principales</span></p>',
        unsafe_allow_html=True,
    )

    img_cards = [
        (
            "hero_data_universe",
            "Observe & Predict",
            "Mart SQLite, KPIs gobernados y ranking de riesgo/demanda con split temporal.",
        ),
        (
            "hero_data_flow",
            "Explain & Decide",
            "SHAP, analista conversacional y motor prescriptivo: a quién priorizar bajo capacidad.",
        ),
        (
            "hero_business_impact",
            "Learn",
            "Experimentos registrados, calidad, eval gold y honestidad sobre límites del sintético.",
        ),
    ]

    cols = st.columns(3, gap="medium")
    for col, (img_name, title, desc) in zip(cols, img_cards):
        with col:
            b64, mime = _img_b64(img_name)
            if b64:
                st.markdown(
                    f"""
                    <div class="landing-image-card"
                         style="background-image:url('data:{mime};base64,{b64}');">
                      <div class="landing-image-overlay">
                        <h3>{title}</h3>
                        <p>{desc}</p>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                # Fallback when image file is absent
                st.markdown(
                    f"""
                    <div class="landing-image-card"
                         style="background:linear-gradient(135deg,#0a2540,#1e3a8a);
                                display:flex;align-items:flex-end;">
                      <div class="landing-image-overlay">
                        <h3>{title}</h3>
                        <p>{desc}</p>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # CTA button ───────────────────────────────────────────────────────────
    st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
    _, cta_col, _ = st.columns([1, 2, 1])
    with cta_col:
        if st.button(
            "Entrar al laboratorio",
            type="primary",
            use_container_width=True,
            key="landing_enter_btn",
        ):
            st.session_state["show_landing"] = False
            st.rerun()

    st.markdown(
        f"""
        <div class="paradigm-footer" style="margin-top:1.5rem;border-top:none;">
          <strong>Paradigm</strong> v{APP_VERSION} · Decision Intelligence Laboratory · {LAST_UPDATE}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── KPI grid ────────────────────────────────────────────────────────────────

def _kpi_card_html(label: str, value: str, delta: str = "") -> str:
    delta_html = f'<div class="kpi-delta">{delta}</div>' if delta else ""
    return (
        f'<div class="kpi-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'{delta_html}</div>'
    )


def render_kpi_grid(kpis: ExecutiveKpis) -> None:
    ns_pct  = f"{kpis.no_show_rate * 100:.1f}%"  if kpis.no_show_rate  is not None else "n/a"
    can_pct = f"{kpis.cancellation_rate * 100:.1f}%" if kpis.cancellation_rate is not None else "n/a"
    revenue_fmt = f"${kpis.revenue:,.0f}"

    row1 = [
        _kpi_card_html("Citas total",    f"{kpis.citas_total:,}"),
        _kpi_card_html("Atendidas",      f"{kpis.attended:,}"),
        _kpi_card_html("No-show rate",   ns_pct, delta=f"{kpis.noshow} no-shows"),
    ]
    row2 = [
        _kpi_card_html("Tasa cancelación", can_pct, delta=f"{kpis.cancelled} canceladas"),
        _kpi_card_html("Ingreso facturado", revenue_fmt, delta="ARS · no VOID"),
        _kpi_card_html("Brechas", f"{kpis.billing_gap_count}", delta="ATTENDED_NO_BILLING"),
    ]
    st.markdown(f'<div class="kpi-grid">{"".join(row1)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-grid">{"".join(row2)}</div>', unsafe_allow_html=True)


def render_gap_card(kpis: ExecutiveKpis) -> None:
    st.markdown(
        f"""
        <div class="gap-highlight">
          <strong style="color:{COLOR_PRIMARY_SOFT};">Brecha de facturación</strong><br/>
          <span style="font-size:1.2rem;font-weight:600;color:{COLOR_TEXT};">
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


# ── Sidebar ─────────────────────────────────────────────────────────────────

def render_sidebar_filters(appointments: pd.DataFrame) -> FilterState:
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
                st.cache_resource.clear()
                st.success("Datos regenerados. Recargando…")
                st.rerun()
            else:
                st.error("Falló la regeneración. Revisá el log.")


# ── Conversational analyst UI ────────────────────────────────────────────────

_ANALYST_PROGRESS: dict[str, str] = {
    "loading":    "Cargando datos…",
    "detecting":  "Detectando estructura…",
    "questions":  "Preparando preguntas relevantes…",
    "understanding": "Entendiendo tu objetivo de negocio…",
    "analyzing":  "Generando análisis contextual…",
}


def render_analyst_progress(phase: str) -> None:
    label = _ANALYST_PROGRESS.get(phase, "Procesando…")
    st.info(label)


def render_analyst_wizard_banner() -> None:
    st.markdown(
        f"""
        <div class="wizard-banner">
          <strong style="color:{COLOR_PRIMARY_SOFT};">Analista Paradigm</strong><br/>
          <span style="color:{COLOR_MUTED};">
            Antes de sacar conclusiones, alineamos objetivo de negocio e hipótesis de causa raíz.
            Son 2–3 preguntas breves (~1 min).
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_schema_brief(ctx) -> None:
    from app.conversational.domain import domain_label_es

    type_counts: dict[str, int] = {}
    for lt in ctx.logical_types.values():
        type_counts[lt] = type_counts.get(lt, 0) + 1
    parts = [f"{k}: {v}" for k, v in sorted(type_counts.items(), key=lambda x: -x[1])]
    c1, c2, c3 = st.columns(3)
    c1.metric("Filas",     f"{ctx.profile.row_count:,}")
    c2.metric("Columnas",  ctx.profile.column_count)
    c3.metric("Dominio",   domain_label_es(ctx.domain)[:22])
    st.caption(
        f"**{ctx.source_label}** · Tipos inferidos: {', '.join(parts[:6])}"
        + (f" · {ctx.profile.null_pct:.1f}% nulos global" if ctx.profile.null_pct else "")
    )


def render_schema_columns_preview(ctx, *, max_cols: int = 12) -> None:
    rows = [
        {"Columna": col, "Tipo": ctx.logical_types.get(col, "—")}
        for col in list(ctx.df.columns)[:max_cols]
    ]
    if len(ctx.df.columns) > max_cols:
        st.caption(f"Mostrando {max_cols} de {len(ctx.df.columns)} columnas.")
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)


def render_guided_questionnaire(
    questions,
    *,
    key_prefix: str,
) -> dict[str, str | float]:
    answers: dict[str, str | float] = {}
    for q in questions:
        with st.container(border=True):
            st.markdown(f"**{q.label}**")
            if q.hint:
                st.caption(q.hint)
            widget_key = f"{key_prefix}_{q.id}"
            if q.widget == "text":
                answers[q.id] = st.text_input(
                    "Tu respuesta",
                    value=str(q.default or ""),
                    key=widget_key,
                    label_visibility="collapsed",
                )
            elif q.widget == "select":
                opts = list(q.options) if q.options else ["—"]
                default_idx = 0
                if q.default and q.default in opts:
                    default_idx = opts.index(q.default)
                answers[q.id] = st.selectbox(
                    "Opción",
                    options=opts,
                    index=default_idx,
                    key=widget_key,
                    label_visibility="collapsed",
                )
            elif q.widget == "number":
                answers[q.id] = st.number_input(
                    "Valor",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(q.default or 10.0),
                    step=1.0,
                    key=widget_key,
                    label_visibility="collapsed",
                )
    return answers


def render_contextual_results(
    result,
    figures,
    *,
    show_ml_cta: bool = False,
    ctx=None,
    plan=None,
    llm_insight: dict | None = None,
    llm_sql_df: pd.DataFrame | None = None,
) -> None:
    """Premium cards: summary, findings, LLM insight, recommendations."""
    st.markdown(f"### {result.title}")

    if ctx is not None:
        objective = None
        if plan is not None and getattr(plan, "objective", None):
            objective = plan.objective
        report_md = build_analysis_report_md(
            result,
            ctx,
            plan_objective=objective,
            llm_insight=llm_insight,
        )
        st.download_button(
            "Exportar reporte MD",
            data=report_md,
            file_name=f"paradigm_analisis_{ctx.dataset_key[:8]}.md",
            mime="text/markdown",
            help="Informe Markdown con análisis contextual + output del AI Analyst.",
            key=f"export_analysis_{ctx.dataset_key}",
        )

    if llm_insight:
        from app.conversational.ai_analyst_ui import render_llm_insight_card

        st.markdown(
            f"<p style='font-weight:600;color:{COLOR_TEXT};margin:0.5rem 0 0.4rem;'>"
            "Análisis del wizard — AI Analyst</p>",
            unsafe_allow_html=True,
        )
        render_llm_insight_card(
            llm_insight,
            title="Primer insight post-wizard",
            sql_df=llm_sql_df,
        )
        st.divider()

    # Summary card
    st.markdown(
        f'<div class="insight-card" style="background:rgba(94,200,212,0.04);">'
        f'{result.summary}</div>',
        unsafe_allow_html=True,
    )

    # Findings
    if result.findings:
        st.markdown(
            f"<p style='font-weight:600;color:{COLOR_TEXT};margin:1rem 0 0.4rem;'>"
            "Hallazgos clave</p>",
            unsafe_allow_html=True,
        )
        for item in result.findings:
            st.markdown(
                f'<div class="finding-item">→&nbsp;{item}</div>',
                unsafe_allow_html=True,
            )

    # Visualisations
    if figures:
        st.markdown(
            f"<p style='font-weight:600;color:{COLOR_TEXT};margin:1rem 0 0.4rem;'>"
            "Visualizaciones</p>",
            unsafe_allow_html=True,
        )
        for i in range(0, len(figures), 2):
            row = figures[i : i + 2]
            cols = st.columns(len(row))
            for j, (_key, fig) in enumerate(row):
                with cols[j]:
                    st.plotly_chart(fig, use_container_width=True)

    # Recommendations with impact badges
    if result.recommendations:
        st.markdown(
            f"<p style='font-weight:600;color:{COLOR_TEXT};margin:1rem 0 0.4rem;'>"
            "Recomendaciones accionables <span style='color:{COLOR_MUTED};"
            "font-weight:400;font-size:0.85rem;'>(priorizadas por impacto)</span></p>",
            unsafe_allow_html=True,
        )
        _badge_map = {
            "Alto":  "badge-high",
            "Medio": "badge-medium",
            "Bajo":  "badge-low",
            "High":  "badge-high",
            "Medium":"badge-medium",
            "Low":   "badge-low",
        }
        for rec in result.recommendations:
            badge_cls = _badge_map.get(str(rec.impact), "badge-low")
            st.markdown(
                f'<div class="insight-card">'
                f'<span class="{badge_cls}">{rec.impact}</span>'
                f'{rec.text}</div>',
                unsafe_allow_html=True,
            )

    if result.data_used:
        st.caption("Datos utilizados: " + ", ".join(f"«{c}»" for c in result.data_used))

    if show_ml_cta:
        st.info(
            "¿Querés simular priorización anti no-show? "
            "Andá a **No-Show ML** en la barra lateral para predicción y explicabilidad SHAP."
        )
