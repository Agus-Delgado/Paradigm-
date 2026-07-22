"""Capa de analista conversacional — Paradigm.

Los símbolos públicos se resuelven de forma perezosa (PEP 562) para que
importar submódulos de lógica (evaluation, nl_to_sql, llm_service, etc.)
no arrastre dependencias de UI/visualización como plotly o streamlit.
"""

from __future__ import annotations

from typing import Any

_LAZY_EXPORTS: dict[str, str] = {
    "run_contextual_analysis": "app.conversational.analysis",
    "DatasetSnapshot": "app.conversational.dataset_snapshot",
    "build_dataset_snapshot": "app.conversational.dataset_snapshot",
    "detect_domain": "app.conversational.domain",
    "domain_label_es": "app.conversational.domain",
    "extract_column_vocabulary": "app.conversational.domain",
    "build_analysis_plan": "app.conversational.plan",
    "build_contextual_plots": "app.conversational.plots",
    "generate_guided_questions": "app.conversational.questions",
    "make_dataset_key": "app.conversational.session_utils",
    "AnalysisPlan": "app.conversational.types",
    "ContextualAnalysisResult": "app.conversational.types",
    "DatasetContext": "app.conversational.types",
    "Domain": "app.conversational.types",
    "GuidedQuestion": "app.conversational.types",
}

__all__ = [
    "AnalysisPlan",
    "ContextualAnalysisResult",
    "DatasetContext",
    "Domain",
    "GuidedQuestion",
    "build_analysis_plan",
    "build_contextual_plots",
    "DatasetSnapshot",
    "build_dataset_snapshot",
    "detect_domain",
    "domain_label_es",
    "extract_column_vocabulary",
    "generate_guided_questions",
    "make_dataset_key",
    "run_contextual_analysis",
]


def __getattr__(name: str) -> Any:
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(module_path)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
