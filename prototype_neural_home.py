"""
Paradigm — Neural Home prototype (isolated).

Experimental cognitive-lab Home. Does not use the main app layout, CSS, or data.

Run:
    streamlit run prototype_neural_home.py
"""

from __future__ import annotations

import html

import streamlit as st

# ── Session keys (prototype-only) ────────────────────────────────────────────
_TASK_KEY = "proto_neural_task"
_ACTIVE_KEY = "proto_neural_active"
_NAV_KEY = "proto_neural_nav"

_STAGES = (
    ("Capture", "Ingest the question as a raw signal"),
    ("Understand", "Shape context and constraints"),
    ("Model", "Form a working hypothesis"),
    ("Evaluate", "Weigh evidence and uncertainty"),
    ("Decide", "Name the next deliberate step"),
)

_NAV = ("Home", "Work", "Assistant", "System")


def _inject_css() -> None:
    st.markdown(
        """
<style>
  @import url("https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap");

  :root {
    --p-bg: #121116;
    --p-surface: #1B1920;
    --p-text: #F1ECE3;
    --p-muted: rgba(241, 236, 227, 0.55);
    --p-faint: rgba(241, 236, 227, 0.28);
    --p-yellow: #D8C46A;
    --p-lavender: #9B8FC4;
    --p-coral: #C9675A;
    --p-green: #719887;
    --p-line: rgba(241, 236, 227, 0.10);
    --p-font: "IBM Plex Sans", "Segoe UI", sans-serif;
    --p-mono: "IBM Plex Mono", "Cascadia Code", monospace;
  }

  html, body, .stApp {
    background: var(--p-bg) !important;
    color: var(--p-text) !important;
    font-family: var(--p-font) !important;
  }

  .stApp {
    background:
      radial-gradient(ellipse 70% 50% at 12% -10%, rgba(155, 143, 196, 0.09), transparent 55%),
      radial-gradient(ellipse 55% 40% at 95% 15%, rgba(216, 196, 106, 0.05), transparent 50%),
      var(--p-bg) !important;
  }

  header[data-testid="stHeader"] { background: transparent !important; }
  #MainMenu, footer { visibility: hidden; }
  [data-testid="stToolbar"] { display: none; }
  [data-testid="stSidebar"] { display: none !important; }
  [data-testid="stSidebarCollapsedControl"] { display: none !important; }

  .main .block-container {
    max-width: 1120px;
    padding: 1.25rem 1.75rem 3.5rem;
  }

  /* ── Top rail ── */
  .p-mark-row {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 0.35rem;
    animation: p-enter 0.5s ease both;
  }

  .p-mark {
    width: 2rem;
    height: 2rem;
    display: grid;
    place-items: center;
    border: 1px solid var(--p-yellow);
    color: var(--p-yellow);
    font-family: var(--p-mono);
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    flex: 0 0 auto;
  }

  .p-mark-meta {
    font-size: 0.68rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--p-faint);
  }

  div[data-testid="stHorizontalBlock"]:first-of-type {
    border-bottom: 1px solid var(--p-line);
    padding-bottom: 0.85rem;
    margin-bottom: 2.5rem;
  }

  div[data-testid="stHorizontalBlock"]:first-of-type .stButton > button {
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    color: var(--p-muted) !important;
    font-family: var(--p-font) !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    padding: 0.35rem 0 !important;
    min-height: 0 !important;
    justify-content: flex-start !important;
    transition: color 0.15s ease !important;
  }

  div[data-testid="stHorizontalBlock"]:first-of-type .stButton > button:hover {
    color: var(--p-text) !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
  }

  div[data-testid="stHorizontalBlock"]:first-of-type .stButton > button[kind="primary"] {
    color: var(--p-text) !important;
    border-bottom: 1px solid var(--p-yellow) !important;
    background: transparent !important;
    font-weight: 600 !important;
  }

  /* ── Core ── */
  .p-brand {
    margin: 0 0 0.85rem !important;
    font-size: clamp(2.6rem, 6vw, 4.1rem) !important;
    font-weight: 700 !important;
    letter-spacing: -0.035em !important;
    line-height: 0.95 !important;
    color: var(--p-text) !important;
    font-family: var(--p-font) !important;
  }

  .p-ask {
    margin: 0 0 1.65rem !important;
    max-width: 22rem;
    font-size: 1.15rem !important;
    font-weight: 400 !important;
    line-height: 1.45 !important;
    color: var(--p-lavender) !important;
  }

  .p-core-zone .stTextInput > div > div {
    background: transparent !important;
    border: none !important;
    border-bottom: 1px solid var(--p-line) !important;
    border-radius: 0 !important;
    box-shadow: none !important;
  }

  .p-core-zone .stTextInput input {
    background: transparent !important;
    color: var(--p-text) !important;
    font-family: var(--p-font) !important;
    font-size: 1.05rem !important;
    padding: 0.65rem 0 !important;
  }

  .p-core-zone .stTextInput input::placeholder {
    color: var(--p-faint) !important;
  }

  .p-core-zone .stTextInput input:focus {
    box-shadow: none !important;
  }

  .p-core-zone .stButton > button[kind="primary"] {
    margin-top: 1.1rem;
    background: var(--p-coral) !important;
    color: var(--p-bg) !important;
    border: none !important;
    border-radius: 0 !important;
    font-family: var(--p-font) !important;
    font-weight: 700 !important;
    letter-spacing: 0.04em;
    padding: 0.65rem 1.35rem !important;
    transition: background 0.18s ease, transform 0.18s ease !important;
    box-shadow: none !important;
  }

  .p-core-zone .stButton > button[kind="primary"]:hover {
    background: #D47868 !important;
    transform: translateY(-1px);
  }

  /* ── Context panel ── */
  .p-context {
    padding-top: 0.35rem;
    border-left: 1px solid var(--p-line);
    padding-left: 1.5rem;
    animation: p-enter 0.55s ease both;
    animation-delay: 120ms;
  }

  .p-context__label {
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--p-faint);
    margin-bottom: 1.1rem;
  }

  .p-context__row {
    display: grid;
    grid-template-columns: 5.2rem minmax(0, 1fr);
    gap: 0.55rem;
    padding: 0.55rem 0;
    border-bottom: 1px solid var(--p-line);
  }

  .p-context__k {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--p-muted);
  }

  .p-context__v {
    font-size: 0.88rem;
    color: var(--p-text);
    line-height: 1.35;
    word-break: break-word;
  }

  .p-context__v--accent { color: var(--p-green); }

  /* ── Flow sequence ── */
  .p-flow-wrap {
    margin: 2.75rem 0 3.25rem;
    animation: p-enter 0.55s ease both;
    animation-delay: 160ms;
  }

  .p-flow-eyebrow {
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--p-faint);
    margin-bottom: 1.25rem;
  }

  .p-flow {
    display: flex;
    align-items: stretch;
    gap: 0;
    position: relative;
  }

  .p-flow::before {
    content: "";
    position: absolute;
    left: 0;
    right: 0;
    top: 1.15rem;
    height: 1px;
    background: linear-gradient(
      90deg,
      var(--p-yellow),
      var(--p-lavender),
      var(--p-green),
      var(--p-coral),
      var(--p-yellow)
    );
    opacity: 0.35;
    pointer-events: none;
  }

  .p-node {
    flex: 1 1 0;
    min-width: 0;
    padding: 0 1rem 0 0;
    position: relative;
  }

  .p-node__dot {
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 50%;
    background: var(--p-surface);
    border: 1px solid var(--p-muted);
    margin-bottom: 1.1rem;
    position: relative;
    z-index: 1;
    transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
  }

  .p-node.is-lit .p-node__dot {
    background: var(--p-yellow);
    border-color: var(--p-yellow);
    box-shadow: 0 0 0 3px rgba(216, 196, 106, 0.15);
  }

  .p-node__idx {
    display: block;
    font-family: var(--p-mono);
    font-size: 0.68rem;
    color: var(--p-faint);
    margin-bottom: 0.3rem;
  }

  .p-node__name {
    display: block;
    font-size: 0.95rem;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--p-muted);
    margin-bottom: 0.35rem;
    transition: color 0.2s ease;
  }

  .p-node.is-lit .p-node__name { color: var(--p-text); }
  .p-node:nth-child(1).is-lit .p-node__name { color: var(--p-yellow); }
  .p-node:nth-child(2).is-lit .p-node__name { color: var(--p-lavender); }
  .p-node:nth-child(3).is-lit .p-node__name { color: var(--p-green); }
  .p-node:nth-child(4).is-lit .p-node__name { color: var(--p-lavender); }
  .p-node:nth-child(5).is-lit .p-node__name { color: var(--p-coral); }

  .p-node__hint {
    display: block;
    font-size: 0.78rem;
    line-height: 1.45;
    color: var(--p-faint);
    max-width: 9.5rem;
  }

  .p-node.is-lit {
    animation: p-enter 0.4s ease both;
    animation-delay: calc(var(--i, 0) * 55ms);
  }

  /* ── Results ── */
  .p-results {
    display: grid;
    grid-template-columns: 1.35fr 1fr 0.95fr;
    gap: 2.5rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--p-line);
    animation: p-enter 0.5s ease both;
    animation-delay: 220ms;
  }

  .p-results.is-empty .p-block__body { color: var(--p-faint); }

  .p-block__tone {
    display: block;
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 0.75rem;
  }

  .p-block--signal .p-block__tone { color: var(--p-yellow); }
  .p-block--evidence .p-block__tone { color: var(--p-lavender); }
  .p-block--action .p-block__tone { color: var(--p-coral); }

  .p-block__title {
    margin: 0 0 0.55rem;
    font-size: 1.35rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    line-height: 1.2;
    color: var(--p-text);
  }

  .p-block__body {
    margin: 0;
    font-size: 0.9rem;
    line-height: 1.55;
    color: var(--p-muted);
    max-width: 22rem;
  }

  .p-block--signal .p-block__title {
    font-size: clamp(1.6rem, 3vw, 2.1rem);
    color: var(--p-yellow);
  }

  .p-task-echo {
    margin: 0 0 1.25rem;
    font-size: 0.85rem;
    color: var(--p-muted);
    animation: p-enter 0.4s ease both;
  }

  .p-task-echo strong {
    color: var(--p-text);
    font-weight: 600;
  }

  .p-placeholder {
    padding: 3rem 0 4rem;
    animation: p-enter 0.45s ease both;
  }

  .p-placeholder__space {
    display: block;
    color: var(--p-yellow);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    font-size: 0.7rem;
    font-weight: 600;
    margin-bottom: 0.75rem;
  }

  @keyframes p-enter {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }

  @media (max-width: 960px) {
    .p-context {
      border-left: none;
      padding-left: 0;
      border-top: 1px solid var(--p-line);
      padding-top: 1.25rem;
      margin-top: 1.5rem;
    }

    .p-flow {
      flex-wrap: wrap;
      gap: 1.25rem 0;
    }

    .p-flow::before { display: none; }

    .p-node {
      flex: 1 1 40%;
      padding-right: 1rem;
    }

    .p-results {
      grid-template-columns: 1fr;
      gap: 1.75rem;
    }
  }

  @media (max-width: 640px) {
    .main .block-container {
      padding: 1rem 1.1rem 2.5rem;
    }

    .p-brand { font-size: 2.4rem !important; }
    .p-node { flex: 1 1 100%; }

    .p-core-zone .stButton > button[kind="primary"] {
      width: 100%;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .p-mark-row, .p-context, .p-flow-wrap, .p-results,
    .p-node.is-lit, .p-task-echo, .p-placeholder {
      animation: none !important;
    }
    .p-core-zone .stButton > button[kind="primary"] {
      transition: none !important;
    }
  }
</style>
        """,
        unsafe_allow_html=True,
    )


def _ensure_state() -> None:
    if _NAV_KEY not in st.session_state:
        st.session_state[_NAV_KEY] = "Home"
    if _ACTIVE_KEY not in st.session_state:
        st.session_state[_ACTIVE_KEY] = False
    if _TASK_KEY not in st.session_state:
        st.session_state[_TASK_KEY] = ""


def _render_top() -> None:
    st.markdown(
        """
        <div class="p-mark-row">
          <div class="p-mark">P</div>
          <div class="p-mark-meta">Cognitive laboratory · prototype</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    active = st.session_state[_NAV_KEY]
    cols = st.columns(len(_NAV))
    for col, item in zip(cols, _NAV):
        with col:
            btn_type = "primary" if item == active else "secondary"
            if st.button(item, key=f"proto_nav_{item}", type=btn_type, use_container_width=True):
                st.session_state[_NAV_KEY] = item
                st.rerun()


def _render_core_and_context() -> None:
    left, right = st.columns([1.55, 0.7])

    with left:
        st.markdown('<div class="p-core-zone">', unsafe_allow_html=True)
        st.markdown(
            """
            <h1 class="p-brand">PARADIGM</h1>
            <p class="p-ask">What do you want to discover?</p>
            """,
            unsafe_allow_html=True,
        )
        st.text_input(
            "Discovery question",
            placeholder="e.g. Where does billing diverge from attended visits?",
            key="proto_input",
            label_visibility="collapsed",
        )
        if st.button("Begin discovery", type="primary", key="proto_cta"):
            text = str(st.session_state.get("proto_input") or "").strip()
            if text:
                st.session_state[_TASK_KEY] = text
                st.session_state[_ACTIVE_KEY] = True
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        mode = "Discovery" if st.session_state[_ACTIVE_KEY] else "Idle"
        st.markdown(
            f"""
            <aside class="p-context">
              <div class="p-context__label">Context</div>
              <div class="p-context__row">
                <span class="p-context__k">Dataset</span>
                <span class="p-context__v">synthetic ambulatory · demo</span>
              </div>
              <div class="p-context__row">
                <span class="p-context__k">Rows</span>
                <span class="p-context__v">12,480</span>
              </div>
              <div class="p-context__row">
                <span class="p-context__k">Model</span>
                <span class="p-context__v">heuristic scaffold</span>
              </div>
              <div class="p-context__row">
                <span class="p-context__k">Mode</span>
                <span class="p-context__v p-context__v--accent">{html.escape(mode)}</span>
              </div>
              <div class="p-context__row">
                <span class="p-context__k">Runtime</span>
                <span class="p-context__v">Local · offline</span>
              </div>
            </aside>
            """,
            unsafe_allow_html=True,
        )


def _render_flow(*, lit: bool) -> None:
    """Render Cognitive Sequence as one HTML block (no indented markdown)."""
    nodes: list[str] = []
    for i, (name, hint) in enumerate(_STAGES):
        cls = "p-node is-lit" if lit else "p-node"
        nodes.append(
            f'<div class="{cls}" style="--i:{i}">'
            f'<div class="p-node__dot" aria-hidden="true"></div>'
            f'<span class="p-node__idx">{i + 1:02d}</span>'
            f'<span class="p-node__name">{html.escape(name)}</span>'
            f'<span class="p-node__hint">{html.escape(hint)}</span>'
            f"</div>"
        )
    sequence_html = (
        '<div class="p-flow-wrap">'
        '<div class="p-flow-eyebrow">Cognitive sequence</div>'
        f'<div class="p-flow" role="list">{"".join(nodes)}</div>'
        "</div>"
    )
    st.markdown(sequence_html, unsafe_allow_html=True)


def _render_results(*, active: bool, task: str) -> None:
    safe_task = html.escape(task)
    if active and task:
        signal = "Billing gap concentration"
        evidence = (
            f"For “{safe_task}”, the prototype highlights attended visits without "
            "matching billing lines as the primary tension in the synthetic mart."
        )
        nxt = "Open a reconciliation pass, then compare specialty-level residuals."
        empty_cls = ""
        st.markdown(
            f'<p class="p-task-echo">Active task · <strong>{safe_task}</strong></p>',
            unsafe_allow_html=True,
        )
    else:
        signal = "Awaiting a question"
        evidence = "Evidence appears once a discovery task is captured."
        nxt = "Write a question above, then begin."
        empty_cls = " is-empty"

    st.markdown(
        f"""
        <div class="p-results{empty_cls}">
          <div class="p-block p-block--signal">
            <span class="p-block__tone">Main Signal</span>
            <h2 class="p-block__title">{html.escape(signal)}</h2>
            <p class="p-block__body">
              One dominant reading — not a dashboard of equal metrics.
            </p>
          </div>
          <div class="p-block p-block--evidence">
            <span class="p-block__tone">Evidence</span>
            <h2 class="p-block__title">Supporting thread</h2>
            <p class="p-block__body">{evidence}</p>
          </div>
          <div class="p-block p-block--action">
            <span class="p-block__tone">Next Action</span>
            <h2 class="p-block__title">Deliberate step</h2>
            <p class="p-block__body">{html.escape(nxt)}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="Paradigm · Neural Home Prototype",
        page_icon="P",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _ensure_state()
    _inject_css()
    _render_top()

    nav = st.session_state[_NAV_KEY]
    if nav != "Home":
        st.markdown(
            f"""
            <div class="p-placeholder">
              <span class="p-placeholder__space">{html.escape(nav)}</span>
              <p class="p-ask">
                This prototype only designs the Home surface.
                {html.escape(nav)} remains a placeholder destination.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    _render_core_and_context()
    active = bool(st.session_state[_ACTIVE_KEY])
    task = str(st.session_state.get(_TASK_KEY) or "")
    _render_flow(lit=active)
    _render_results(active=active, task=task)


if __name__ == "__main__":
    main()
