"""UI minima de Paradigm Copilot.

No ejecuta codigo. Las propuestas requieren revision humana.
"""

from __future__ import annotations

import html

import streamlit as st

from app.conversational.copilot_contract import CopilotRequest, CopilotTask
from app.conversational.copilot_service import CopilotServiceError, generate_copilot_response
from app.ui import render_module_context


_TASK_LABELS: list[tuple[str, CopilotTask]] = [
    ("Explain SQL", CopilotTask.EXPLAIN_SQL),
    ("Review SQL", CopilotTask.REVIEW_SQL),
    ("Explain Python", CopilotTask.EXPLAIN_PYTHON),
    ("Analyze Error", CopilotTask.ANALYZE_ERROR),
    ("Propose Fix", CopilotTask.PROPOSE_FIX),
]

_CONTENT_LABEL_BY_TASK: dict[CopilotTask, str] = {
    CopilotTask.EXPLAIN_SQL: "SQL",
    CopilotTask.REVIEW_SQL: "SQL to review",
    CopilotTask.EXPLAIN_PYTHON: "Python code",
    CopilotTask.ANALYZE_ERROR: "Related code or snippet",
    CopilotTask.PROPOSE_FIX: "Code or query to improve",
}


def _flow_items_html(items: list | None, *, empty: str) -> str:
    rows = [str(x).strip() for x in (items or []) if str(x).strip()]
    if not rows:
        return f'<p class="pd-copilot-flow-empty">{html.escape(empty)}</p>'
    lis = "".join(f"<li>{html.escape(row)}</li>" for row in rows)
    return f'<ul class="pd-copilot-flow-list">{lis}</ul>'


def _render_response() -> None:
    payload = st.session_state.get("paradigm_copilot_last_response")
    if not isinstance(payload, dict):
        return

    input_content = str(payload.get("input_content") or "").strip()
    input_context = str(payload.get("input_context") or "").strip()
    input_error = str(payload.get("input_error") or "").strip()
    summary = str(payload.get("summary") or "").strip()
    explanation = payload.get("explanation") or []
    issues = payload.get("issues") or []
    suggested_fix = payload.get("suggested_fix")
    risks = payload.get("risks") or []
    requires_review = bool(payload.get("requires_review", True))

    input_parts: list[str] = []
    if input_content:
        input_parts.append(
            f'<pre class="pd-copilot-flow-code">{html.escape(input_content)}</pre>'
        )
    else:
        input_parts.append(
            '<p class="pd-copilot-flow-empty">No input content captured.</p>'
        )
    if input_context:
        input_parts.append(
            f'<p class="pd-copilot-flow-meta"><span>Context</span>{html.escape(input_context)}</p>'
        )
    if input_error:
        input_parts.append(
            f'<p class="pd-copilot-flow-meta"><span>Error</span>{html.escape(input_error)}</p>'
        )
    input_body = "".join(input_parts)

    analysis_parts: list[str] = [
        f'<p class="pd-copilot-flow-summary">'
        f'{html.escape(summary) if summary else "No summary returned."}'
        f"</p>"
    ]
    if explanation:
        analysis_parts.append(_flow_items_html(explanation, empty=""))

    proposal_body = (
        f'<pre class="pd-copilot-flow-code">{html.escape(str(suggested_fix))}</pre>'
        if suggested_fix
        else '<p class="pd-copilot-flow-empty">No suggested fix returned.</p>'
    )
    review_note = (
        "Yes. Review all outputs before applying any change."
        if requires_review
        else "Yes. Human review remains required."
    )
    risk_tail = f'<p class="pd-copilot-flow-review">{html.escape(review_note)}</p>'

    # Compact single-string HTML (avoids Streamlit markdown indent → visible tags).
    flow_html = (
        '<div class="pd-copilot-flow">'
        '<div class="pd-copilot-flow-rail" aria-hidden="true">'
        '<span class="pd-copilot-flow-rail__node pd-copilot-flow-rail__node--signal">Input</span>'
        '<span class="pd-copilot-flow-rail__link"></span>'
        '<span class="pd-copilot-flow-rail__node pd-copilot-flow-rail__node--interpretation">Analysis</span>'
        '<span class="pd-copilot-flow-rail__link"></span>'
        '<span class="pd-copilot-flow-rail__node pd-copilot-flow-rail__node--risk">Issues</span>'
        '<span class="pd-copilot-flow-rail__link"></span>'
        '<span class="pd-copilot-flow-rail__node pd-copilot-flow-rail__node--decision">Proposal</span>'
        '<span class="pd-copilot-flow-rail__link"></span>'
        '<span class="pd-copilot-flow-rail__node pd-copilot-flow-rail__node--risk">Risk</span>'
        "</div>"
        '<section class="pd-copilot-flow-stage pd-copilot-flow-stage--signal">'
        '<header class="pd-copilot-flow-stage__head">'
        '<span class="pd-copilot-flow-stage__index">01</span>'
        '<span class="pd-copilot-flow-stage__label">Input</span>'
        "</header>"
        f'<div class="pd-copilot-flow-stage__body">{input_body}</div>'
        "</section>"
        '<section class="pd-copilot-flow-stage pd-copilot-flow-stage--interpretation">'
        '<header class="pd-copilot-flow-stage__head">'
        '<span class="pd-copilot-flow-stage__index">02</span>'
        '<span class="pd-copilot-flow-stage__label">Analysis</span>'
        "</header>"
        f'<div class="pd-copilot-flow-stage__body">{"".join(analysis_parts)}</div>'
        "</section>"
        '<section class="pd-copilot-flow-stage pd-copilot-flow-stage--risk">'
        '<header class="pd-copilot-flow-stage__head">'
        '<span class="pd-copilot-flow-stage__index">03</span>'
        '<span class="pd-copilot-flow-stage__label">Issues</span>'
        "</header>"
        '<div class="pd-copilot-flow-stage__body">'
        f'{_flow_items_html(issues, empty="No issues reported.")}'
        "</div>"
        "</section>"
        '<section class="pd-copilot-flow-stage pd-copilot-flow-stage--decision">'
        '<header class="pd-copilot-flow-stage__head">'
        '<span class="pd-copilot-flow-stage__index">04</span>'
        '<span class="pd-copilot-flow-stage__label">Proposal</span>'
        "</header>"
        f'<div class="pd-copilot-flow-stage__body">{proposal_body}</div>'
        "</section>"
        '<section class="pd-copilot-flow-stage pd-copilot-flow-stage--risk">'
        '<header class="pd-copilot-flow-stage__head">'
        '<span class="pd-copilot-flow-stage__index">05</span>'
        '<span class="pd-copilot-flow-stage__label">Risk</span>'
        "</header>"
        '<div class="pd-copilot-flow-stage__body">'
        f'{_flow_items_html(risks, empty="No risks reported.")}'
        f"{risk_tail}"
        "</div>"
        "</section>"
        "</div>"
    )
    st.markdown(flow_html, unsafe_allow_html=True)


def render_copilot_page() -> None:
    st.markdown(
        '<div class="pd-copilot-intake">'
        '<div class="pd-copilot-intake__eyebrow">Copilot sequence</div>'
        '<div class="pd-copilot-intake__rail" role="list">'
        '<span class="pd-copilot-intake__node pd-copilot-intake__node--signal">Input</span>'
        '<span class="pd-copilot-intake__link" aria-hidden="true"></span>'
        '<span class="pd-copilot-intake__node pd-copilot-intake__node--interpretation">Analysis</span>'
        '<span class="pd-copilot-intake__link" aria-hidden="true"></span>'
        '<span class="pd-copilot-intake__node pd-copilot-intake__node--risk">Issues</span>'
        '<span class="pd-copilot-intake__link" aria-hidden="true"></span>'
        '<span class="pd-copilot-intake__node pd-copilot-intake__node--decision">Proposal</span>'
        '<span class="pd-copilot-intake__link" aria-hidden="true"></span>'
        '<span class="pd-copilot-intake__node pd-copilot-intake__node--risk">Risk</span>'
        "</div>"
        '<p class="pd-copilot-intake__note">'
        "Technical companion for SQL, Python and errors. "
        "No code execution — every proposal needs human review."
        "</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    render_module_context(
        name="Copilot",
        stage="Action",
        purpose=(
            "Compañero técnico para explicar y revisar SQL, Python y errores. "
            "No ejecuta código; toda propuesta requiere revisión humana."
        ),
        status="Active",
        capabilities=(
            "Explain / Review SQL",
            "Explain Python",
            "Analyze Error y Propose Fix",
            "Salida estructurada con riesgos explícitos",
        ),
        limitations=(
            "Sin ejecución de SQL o Python",
            "Sin edición de archivos ni historial persistente",
            "Depende del proveedor LLM configurado",
        ),
    )

    st.markdown(
        '<div class="pd-copilot-intake__label">Task</div>',
        unsafe_allow_html=True,
    )
    labels = [label for label, _ in _TASK_LABELS]
    selected_label = st.selectbox("Task", labels, index=0, label_visibility="collapsed")
    task_map = {label: task for label, task in _TASK_LABELS}
    selected_task = task_map[selected_label]

    st.markdown(
        f'<div class="pd-copilot-intake__label">{html.escape(_CONTENT_LABEL_BY_TASK[selected_task])}</div>',
        unsafe_allow_html=True,
    )
    content = st.text_area(
        _CONTENT_LABEL_BY_TASK[selected_task],
        placeholder="Paste SQL, Python, traceback, or snippet to analyze.",
        height=220,
        label_visibility="collapsed",
    )

    st.markdown(
        '<div class="pd-copilot-intake__label">Context <span>(optional)</span></div>',
        unsafe_allow_html=True,
    )
    context = st.text_area(
        "Context (optional)",
        placeholder="Optional: business objective, schema notes, assumptions, or relevant context.",
        height=120,
        label_visibility="collapsed",
    )

    error_message: str | None = None
    if selected_task is CopilotTask.ANALYZE_ERROR:
        st.markdown(
            '<div class="pd-copilot-intake__label">Error message</div>',
            unsafe_allow_html=True,
        )
        error_message = st.text_area(
            "Error message",
            placeholder="Required for Analyze Error. Example: KeyError: 'status_code'",
            height=100,
            label_visibility="collapsed",
        )

    if st.button("Analyze", type="primary"):
        try:
            req = CopilotRequest(
                task=selected_task,
                content=content,
                context=context or None,
                error_message=error_message or None,
            )
            with st.spinner("Analyzing with Paradigm Copilot..."):
                response = generate_copilot_response(req)
            st.session_state["paradigm_copilot_last_response"] = {
                "input_content": content,
                "input_context": (context or "").strip(),
                "input_error": (error_message or "").strip(),
                "summary": response.summary,
                "explanation": list(response.explanation),
                "issues": list(response.issues),
                "suggested_fix": response.suggested_fix,
                "risks": list(response.risks),
                "requires_review": response.requires_review,
            }
        except ValueError as exc:
            st.error(str(exc))
        except CopilotServiceError as exc:
            st.error(str(exc))

    _render_response()
