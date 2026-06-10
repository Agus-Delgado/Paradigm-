"""Capa de analista conversacional — Paradigm."""

from app.conversational.analysis import run_contextual_analysis
from app.conversational.dataset_snapshot import DatasetSnapshot, build_dataset_snapshot
from app.conversational.domain import detect_domain, domain_label_es, extract_column_vocabulary
from app.conversational.plan import build_analysis_plan
from app.conversational.plots import build_contextual_plots
from app.conversational.questions import generate_guided_questions
from app.conversational.session_utils import make_dataset_key
from app.conversational.types import (
    AnalysisPlan,
    ContextualAnalysisResult,
    DatasetContext,
    Domain,
    GuidedQuestion,
)

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
