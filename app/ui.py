"""Componentes UI: tema premium dark, KPI cards, landing page y wizard."""

from __future__ import annotations

import base64
import html
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from app.config import (
    APP_VERSION,
    COLOR_MUTED,
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
    """Meta compacta bajo el contexto Observatory del módulo (sin título duplicado)."""
    st.markdown(
        f'<div class="pd-module-workspace-meta">'
        f'<span class="pd-module-workspace-meta__title">{title}</span>'
        f'<span class="pd-module-workspace-meta__detail">{meta}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def render_module_context(
    *,
    name: str,
    stage: str,
    purpose: str,
    status: str,
    capabilities: list[str] | tuple[str, ...],
    limitations: list[str] | tuple[str, ...],
) -> None:
    """Notas del módulo; título/etapa/propósito viven en render_page_header."""
    del name, stage, purpose, status
    caps = "".join(f"<li>{html.escape(item)}</li>" for item in capabilities)
    lims = "".join(f"<li>{html.escape(item)}</li>" for item in limitations)
    st.markdown(
        '<div class="pd-page-notes">'
        '<div class="pd-page-notes__col">'
        '<div class="pd-page-notes__label">Capabilities</div>'
        f'<ul class="pd-page-notes__list">{caps}</ul>'
        "</div>"
        '<div class="pd-page-notes__col">'
        '<div class="pd-page-notes__label">Limitations</div>'
        f'<ul class="pd-page-notes__list">{lims}</ul>'
        "</div>"
        "</div>",
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


# ── Global chrome (mineral) ──────────────────────────────────────────────────

_TOP_NAV: tuple[tuple[str, str], ...] = (
    ("Home", "Home"),
    ("Work", "Workspaces"),
    ("Assistant", "Assistant"),
    ("System", "System"),
)


def render_global_topbar(active_space: str) -> None:
    """Barra mínima: marca P · Home · Work · Assistant · System."""
    st.markdown(
        '<div class="pd-topbar">'
        '<div class="pd-topbar__brand">'
        '<div class="pd-topbar__mark">P</div>'
        '<span class="pd-topbar__meta">Paradigm</span>'
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(len(_TOP_NAV))
    for col, (label, space) in zip(cols, _TOP_NAV):
        with col:
            is_on = active_space == space
            if st.button(
                label,
                key=f"pd_top_{label}",
                type="primary" if is_on else "secondary",
                use_container_width=True,
            ):
                if space == "Home":
                    navigate_to("Home")
                elif space == "Workspaces":
                    navigate_to("Workspaces", "Data & Quality")
                elif space == "Assistant":
                    navigate_to("Assistant", "Paradigm Assistant")
                else:
                    navigate_to("System", "Automation Lab")


def render_page_header(
    *,
    section: str,
    title: str,
    purpose: str,
    stage: str,
    status: str = "",
) -> None:
    """Header compacto compartido por páginas internas."""
    status_html = (
        f'<span class="pd-page-header__status">{html.escape(status)}</span>'
        if status
        else ""
    )
    st.markdown(
        '<div class="pd-page-header">'
        '<div class="pd-page-header__row">'
        f'<span class="pd-page-header__section">{html.escape(section)}</span>'
        f'<span class="pd-page-header__stage">{html.escape(stage)}</span>'
        f"{status_html}"
        "</div>"
        f'<h1 class="pd-page-header__title">{html.escape(title)}</h1>'
        f'<p class="pd-page-header__purpose">{html.escape(purpose)}</p>'
        "</div>",
        unsafe_allow_html=True,
    )


# ── Home (prototype composition · real data) ─────────────────────────────────

_SPACE_KEY = "paradigm_active_space"
_VIEW_KEY = "paradigm_active_view"
_PENDING_TASK_KEY = "paradigm_pending_task"
_RECENT_TASKS_KEY = "paradigm_recent_tasks"
_RECENT_TASKS_MAX = 3
_HOME_LIT_KEY = "paradigm_home_sequence_lit"

_COGNITIVE_STAGES: tuple[tuple[str, str], ...] = (
    ("Capture", "Ingest the question as a raw signal"),
    ("Understand", "Shape context and constraints"),
    ("Model", "Form a working hypothesis"),
    ("Evaluate", "Weigh evidence and uncertainty"),
    ("Decide", "Name the next deliberate step"),
)

_HOME_LAUNCHER: tuple[dict[str, str], ...] = (
    {"title": "Data & Quality", "space": "Workspaces", "view": "Data & Quality"},
    {"title": "No-Show", "space": "Workspaces", "view": "No-Show Intelligence"},
    {"title": "Forecasting", "space": "Workspaces", "view": "Forecasting"},
    {"title": "Assistant", "space": "Assistant", "view": "Paradigm Assistant"},
    {"title": "Copilot", "space": "Assistant", "view": "Copilot"},
    {"title": "Automation", "space": "System", "view": "Automation Lab"},
    {"title": "Governance", "space": "System", "view": "Governance & Improvement"},
)
_HOME_CAPABILITIES = _HOME_LAUNCHER


def push_recent_task(text: str) -> None:
    cleaned = text.strip()
    if not cleaned:
        return
    recent = list(st.session_state.get(_RECENT_TASKS_KEY) or [])
    if recent and recent[0] == cleaned:
        return
    recent = [cleaned, *[t for t in recent if t != cleaned]]
    st.session_state[_RECENT_TASKS_KEY] = recent[:_RECENT_TASKS_MAX]


def get_recent_tasks() -> list[str]:
    raw = st.session_state.get(_RECENT_TASKS_KEY) or []
    if not isinstance(raw, list):
        return []
    return [str(t) for t in raw if str(t).strip()][:_RECENT_TASKS_MAX]


def navigate_to(space: str, view: str | None = None) -> None:
    st.session_state[_SPACE_KEY] = space
    if view:
        st.session_state[_VIEW_KEY] = view
    elif space == "Home":
        st.session_state[_VIEW_KEY] = ""
    st.rerun()


def render_home_surface_styles() -> None:
    """Home shares the global mineral shell; no scoped :has() marker."""
    return


def render_home_mark_bar() -> None:
    """Mark lives in the global topbar."""
    return


def render_home_core_and_context(
    *,
    filters: FilterState | None,
    db_name: str,
    llm_provider: str,
    appointment_count: int,
    filtered_rows: int,
    input_key: str = "paradigm_home_command_input",
    button_key: str = "paradigm_home_find_path",
) -> None:
    lit = bool(st.session_state.get(_HOME_LIT_KEY) or st.session_state.get(_PENDING_TASK_KEY))
    mode = "Discovery" if lit else "Observe"
    if filters is not None:
        dataset = (
            f"mart filtrado · {filters.date_start.date()} → {filters.date_end.date()}"
        )
    else:
        dataset = "mart SQLite local"
    left, right = st.columns([1.55, 0.7])
    with left:
        st.markdown('<div class="pd-home-core">', unsafe_allow_html=True)
        st.markdown(
            '<h1 class="pd-home-brand">PARADIGM</h1>'
            '<p class="pd-home-ask">What do you want to discover?</p>',
            unsafe_allow_html=True,
        )
        st.text_input(
            "Discovery question",
            placeholder="e.g. Where does billing diverge from attended visits?",
            key=input_key,
            label_visibility="collapsed",
        )
        if st.button("Begin discovery", type="primary", key=button_key):
            text = str(st.session_state.get(input_key) or "").strip()
            if not text:
                st.warning("Escribí una pregunta u objetivo breve.")
            else:
                st.session_state[_PENDING_TASK_KEY] = text
                push_recent_task(text)
                st.session_state[_HOME_LIT_KEY] = True
                st.session_state[_SPACE_KEY] = "Assistant"
                st.session_state[_VIEW_KEY] = "Paradigm Assistant"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        context_html = (
            '<aside class="pd-home-context">'
            '<div class="pd-home-context__label">Context</div>'
            '<div class="pd-home-context__row">'
            '<span class="pd-home-context__k">Dataset</span>'
            f'<span class="pd-home-context__v">{html.escape(dataset)}</span>'
            "</div>"
            '<div class="pd-home-context__row">'
            '<span class="pd-home-context__k">Rows</span>'
            f'<span class="pd-home-context__v">{filtered_rows:,} · mart {appointment_count:,}</span>'
            "</div>"
            '<div class="pd-home-context__row">'
            '<span class="pd-home-context__k">SQLite</span>'
            f'<span class="pd-home-context__v">{html.escape(db_name)}</span>'
            "</div>"
            '<div class="pd-home-context__row">'
            '<span class="pd-home-context__k">LLM</span>'
            f'<span class="pd-home-context__v">{html.escape(str(llm_provider))}</span>'
            "</div>"
            '<div class="pd-home-context__row">'
            '<span class="pd-home-context__k">Mode</span>'
            f'<span class="pd-home-context__v pd-home-context__v--accent">{html.escape(mode)}</span>'
            "</div>"
            '<div class="pd-home-context__row">'
            '<span class="pd-home-context__k">Runtime</span>'
            '<span class="pd-home-context__v">Local</span>'
            "</div>"
            "</aside>"
        )
        st.markdown(context_html, unsafe_allow_html=True)


def render_cognitive_sequence(*, lit: bool) -> None:
    nodes: list[str] = []
    for i, (name, hint) in enumerate(_COGNITIVE_STAGES):
        cls = "pd-home-node is-lit" if lit else "pd-home-node"
        nodes.append(
            f'<div class="{cls}" style="--i:{i}">'
            f'<div class="pd-home-node__dot" aria-hidden="true"></div>'
            f'<span class="pd-home-node__idx">{i + 1:02d}</span>'
            f'<span class="pd-home-node__name">{html.escape(name)}</span>'
            f'<span class="pd-home-node__hint">{html.escape(hint)}</span>'
            f"</div>"
        )
    sequence_html = (
        '<div class="pd-home-flow-wrap">'
        '<div class="pd-home-flow-eyebrow">Cognitive sequence</div>'
        f'<div class="pd-home-flow" role="list">{"".join(nodes)}</div>'
        "</div>"
    )
    st.markdown(sequence_html, unsafe_allow_html=True)


def render_home_launcher() -> None:
    st.markdown(
        '<div class="pd-home-launcher">'
        '<div class="pd-home-flow-eyebrow">Open a workspace</div>'
        "</div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    for idx, item in enumerate(_HOME_LAUNCHER):
        with cols[idx % 4]:
            btn_key = (
                f"pd_home_nav_{item['space']}_{item['view']}"
                .replace(" ", "_")
                .replace("&", "and")
            )
            if st.button(item["title"], key=btn_key, use_container_width=True):
                navigate_to(item["space"], item["view"])


def render_home_results(*, kpis: ExecutiveKpis | None, task: str) -> None:
    safe_task = html.escape(task.strip()) if task else ""
    if kpis is None:
        signal = "No appointments in filter"
        evidence = "Adjust sidebar filters to restore mart signals."
        nxt = "Widen the date range or clear specialty filters."
        empty_cls = " is-empty"
    else:
        ns = (
            f"{kpis.no_show_rate * 100:.1f}%"
            if kpis.no_show_rate is not None
            else "n/a"
        )
        signal = f"{kpis.citas_total:,} visits"
        evidence = (
            f"{kpis.attended:,} attended · no-show {ns} · "
            f"billing gap {kpis.billing_gap_count:,} "
            f"(${kpis.billing_gap_amount:,.0f} ARS)"
        )
        if kpis.billing_gap_count > 0:
            nxt = "Open Data & Quality to inspect ATTENDED_NO_BILLING."
        elif kpis.no_show_rate is not None and kpis.no_show_rate >= 0.1:
            nxt = "Open No-Show Intelligence to prioritize risk."
        else:
            nxt = "Ask Assistant a question, or open Forecasting for demand."
        empty_cls = ""
    if safe_task:
        st.markdown(
            f'<p class="pd-home-task-echo">Active task · <strong>{safe_task}</strong></p>',
            unsafe_allow_html=True,
        )
    results_html = (
        f'<div class="pd-home-results{empty_cls}">'
        '<div class="pd-home-block pd-home-block--signal">'
        '<span class="pd-home-block__tone">Main Signal</span>'
        f'<h2 class="pd-home-block__title">{html.escape(signal)}</h2>'
        '<p class="pd-home-block__body">Dominant volume under current filters.</p>'
        "</div>"
        '<div class="pd-home-block pd-home-block--evidence">'
        '<span class="pd-home-block__tone">Evidence</span>'
        '<h2 class="pd-home-block__title">Supporting thread</h2>'
        f'<p class="pd-home-block__body">{html.escape(evidence)}</p>'
        "</div>"
        '<div class="pd-home-block pd-home-block--action">'
        '<span class="pd-home-block__tone">Next Action</span>'
        '<h2 class="pd-home-block__title">Deliberate step</h2>'
        f'<p class="pd-home-block__body">{html.escape(nxt)}</p>'
        "</div>"
        "</div>"
    )
    st.markdown(results_html, unsafe_allow_html=True)


def render_process_rail(
    stages: list[dict[str, str]],
    *,
    rail_class: str = "pd-process-rail",
) -> None:
    """Secuencia visual de proceso (nodos + enlaces), HTML compacto."""
    parts: list[str] = []
    for i, stage in enumerate(stages):
        if i:
            parts.append('<div class="pd-process-link" aria-hidden="true"></div>')
        tone = html.escape(stage.get("tone", "structure"))
        status = html.escape(stage.get("status", ""))
        label = html.escape(stage.get("label", ""))
        detail = html.escape(stage.get("detail", ""))
        count = stage.get("count", "")
        count_html = (
            f'<span class="pd-process-step__count">{html.escape(str(count))}</span>'
            if count != "" and count is not None
            else ""
        )
        status_html = (
            f'<span class="pd-process-step__status">{status}</span>' if status else ""
        )
        status_cls = f" pd-process-step--{status}" if status else ""
        live_cls = " pd-process-step--live" if status == "active" else ""
        parts.append(
            f'<div class="pd-process-step pd-process-step--{tone}{status_cls}{live_cls}" '
            f'style="--pd-step-i:{i}">'
            f'<span class="pd-process-step__label">{label}</span>'
            f"{status_html}{count_html}"
            f'<span class="pd-process-step__detail">{detail}</span>'
            "</div>"
        )
    st.markdown(
        f'<div class="{html.escape(rail_class)}">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


def render_data_quality_process(
    *,
    attended: int,
    gap_n: int,
    with_billing: int,
    pending: int,
) -> None:
    """Resumen visual Source → Validation → Reconciliation → Evidence."""
    st.markdown(
        '<div class="pd-section-heading">Quality sequence</div>',
        unsafe_allow_html=True,
    )
    render_process_rail(
        [
            {
                "label": "Source",
                "tone": "signal",
                "status": "active",
                "detail": "Mart filtrado · citas atendidas",
                "count": f"{attended:,}",
            },
            {
                "label": "Validation",
                "tone": "structure",
                "status": "active",
                "detail": "Buckets ATTENDED_*",
                "count": f"{with_billing + pending + gap_n:,}",
            },
            {
                "label": "Reconciliation",
                "tone": "interpretation",
                "status": "active",
                "detail": "Con billing / pendiente",
                "count": f"{with_billing:,} / {pending:,}",
            },
            {
                "label": "Evidence",
                "tone": "risk" if gap_n else "signal",
                "status": "active",
                "detail": "ATTENDED_NO_BILLING",
                "count": f"{gap_n:,}",
            },
        ]
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
                         style="background:linear-gradient(135deg,#0B1622,#1C2E40);
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


# ── Sidebar ─────────────────────────────────────────────────────────────────

def render_sidebar_filters(appointments: pd.DataFrame) -> FilterState:
    """Filtros del mart. Usar dentro de `st.sidebar` o un expander del sidebar."""
    min_d = appointments["appointment_date"].min().date()
    max_d = appointments["appointment_date"].max().date()

    date_range = st.date_input(
        "Rango de fechas (cita)",
        value=(min_d, max_d),
        min_value=min_d,
        max_value=max_d,
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        date_start, date_end = date_range
    else:
        date_start = date_end = date_range if isinstance(date_range, date) else min_d

    specialties = st.multiselect(
        "Especialidad",
        options=sorted(appointments["specialty_name"].dropna().unique()),
    )
    providers = st.multiselect(
        "Proveedor",
        options=sorted(appointments["provider_label"].dropna().unique()),
    )
    channels = st.multiselect(
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
    """Controles de regeneración. Usar dentro de un expander de Mantenimiento."""
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
        '<div class="pd-wizard-banner">'
        '<div class="pd-wizard-banner__label">Business alignment</div>'
        '<p class="pd-wizard-banner__note">'
        "Antes de interpretar señales, alineamos objetivo de negocio e hipótesis. "
        "Son 2–3 preguntas breves (~1 min)."
        "</p>"
        "</div>",
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
        hint_html = (
            f'<p class="pd-wizard-q__hint">{html.escape(q.hint)}</p>' if q.hint else ""
        )
        st.markdown(
            f'<div class="pd-wizard-q">'
            f'<div class="pd-wizard-q__label">{html.escape(q.label)}</div>'
            f"{hint_html}"
            "</div>",
            unsafe_allow_html=True,
        )
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
            '<div class="pd-results-label">Análisis del wizard — AI Analyst</div>',
            unsafe_allow_html=True,
        )
        render_llm_insight_card(
            llm_insight,
            title="Primer insight post-wizard",
            sql_df=llm_sql_df,
        )
        st.divider()

    # Summary
    st.markdown(
        f'<div class="insight-card">{html.escape(str(result.summary))}</div>',
        unsafe_allow_html=True,
    )

    # Findings
    if result.findings:
        st.markdown(
            '<div class="pd-results-label">Hallazgos clave</div>',
            unsafe_allow_html=True,
        )
        for item in result.findings:
            st.markdown(
                f'<div class="finding-item">→&nbsp;{html.escape(str(item))}</div>',
                unsafe_allow_html=True,
            )

    # Visualisations
    if figures:
        st.markdown(
            '<div class="pd-results-label">Visualizaciones</div>',
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
            '<div class="pd-results-label">Recomendaciones accionables '
            '<span class="pd-results-label__meta">(priorizadas por impacto)</span></div>',
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
                f'<span class="{badge_cls}">{html.escape(str(rec.impact))}</span>'
                f'{html.escape(str(rec.text))}</div>',
                unsafe_allow_html=True,
            )

    if result.data_used:
        st.caption("Datos utilizados: " + ", ".join(f"«{c}»" for c in result.data_used))

    if show_ml_cta:
        st.info(
            "¿Querés simular priorización anti no-show? "
            "Andá a **No-Show ML** en la barra lateral para predicción y explicabilidad SHAP."
        )
