"""UI minima de Paradigm Copilot.

No ejecuta codigo. Las propuestas requieren revision humana.
"""

from __future__ import annotations

import streamlit as st

from app.conversational.copilot_contract import CopilotRequest, CopilotTask
from app.conversational.copilot_service import CopilotServiceError, generate_copilot_response


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


def _render_response() -> None:
    payload = st.session_state.get("paradigm_copilot_last_response")
    if not isinstance(payload, dict):
        return

    st.subheader("Summary")
    st.markdown(payload.get("summary", ""))

    st.subheader("Explanation")
    explanation = payload.get("explanation") or []
    if explanation:
        for item in explanation:
            st.markdown(f"- {item}")
    else:
        st.info("No explanation details returned.")

    st.subheader("Issues")
    issues = payload.get("issues") or []
    if issues:
        for item in issues:
            st.markdown(f"- {item}")
    else:
        st.info("No issues reported.")

    st.subheader("Suggested Fix")
    suggested_fix = payload.get("suggested_fix")
    if suggested_fix:
        st.code(str(suggested_fix), language="text")
    else:
        st.warning("No suggested fix returned.")

    st.subheader("Risks")
    risks = payload.get("risks") or []
    if risks:
        for item in risks:
            st.markdown(f"- {item}")
    else:
        st.info("No risks reported.")

    st.subheader("Human Review Required")
    if bool(payload.get("requires_review", True)):
        st.warning("Yes. Review all outputs before applying any change.")
    else:
        st.warning("Yes. Human review remains required.")


def render_copilot_page() -> None:
    st.header("Paradigm Copilot")
    st.caption(
        "Companero tecnico para explicar y revisar SQL, Python y errores. "
        "No ejecuta codigo y sus propuestas requieren revision humana."
    )

    labels = [label for label, _ in _TASK_LABELS]
    selected_label = st.selectbox("Task", labels, index=0)
    task_map = {label: task for label, task in _TASK_LABELS}
    selected_task = task_map[selected_label]

    content = st.text_area(
        _CONTENT_LABEL_BY_TASK[selected_task],
        placeholder="Paste SQL, Python, traceback, or snippet to analyze.",
        height=220,
    )

    context = st.text_area(
        "Context (optional)",
        placeholder="Optional: business objective, schema notes, assumptions, or relevant context.",
        height=120,
    )

    error_message: str | None = None
    if selected_task is CopilotTask.ANALYZE_ERROR:
        error_message = st.text_area(
            "Error message",
            placeholder="Required for Analyze Error. Example: KeyError: 'status_code'",
            height=100,
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