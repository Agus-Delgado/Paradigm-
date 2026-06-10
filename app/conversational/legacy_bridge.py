"""Puente hacia módulos core del explorador legacy v1."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LEGACY_APP = REPO_ROOT / "legacy" / "app"
DEMO_CLINIC_CSV = (
    REPO_ROOT / "legacy" / "data" / "sample" / "medical_clinic" / "medical_clinic_flat.csv"
)

_path_ready = False


def ensure_legacy_path() -> None:
    global _path_ready
    if _path_ready:
        return
    legacy_str = str(LEGACY_APP)
    if legacy_str not in sys.path:
        sys.path.insert(0, legacy_str)
    _path_ready = True


def infer_logical_types(df):
    ensure_legacy_path()
    from core.schema import infer_logical_types as _fn

    return _fn(df)


def build_profile(df, logical_types):
    ensure_legacy_path()
    from core.profiling import build_profile as _fn

    return _fn(df, logical_types)


def build_findings(df, profile, logical_types):
    ensure_legacy_path()
    from core.findings import build_findings as _fn

    return _fn(df, profile, logical_types)


def load_uploaded_file(uploaded_file):
    ensure_legacy_path()
    from core.ingestion import load_uploaded_file as _fn

    return _fn(uploaded_file)


def load_csv_path(path):
    ensure_legacy_path()
    from core.ingestion import load_csv_path as _fn

    return _fn(path)


def clinic_kpis_available(df) -> bool:
    ensure_legacy_path()
    from core.clinic_operational_kpis import clinic_kpis_available as _fn

    return _fn(df)


def compute_clinic_kpis(df):
    ensure_legacy_path()
    from core.clinic_operational_kpis import compute_clinic_kpis as _fn

    return _fn(df)


def run_conversational_analysis(query, df, logical_types, profile, findings=None):
    ensure_legacy_path()
    from core.ai_analytics import run_conversational_analysis as _fn

    return _fn(query, df, logical_types, profile, findings=findings)


def insights_build_dataset_overview(df, profile, logical_types):
    ensure_legacy_path()
    from core.ai_analytics.insights import build_dataset_overview as _fn

    return _fn(df, profile, logical_types)


def insights_top_categories(df, logical_types, limit_cols=3):
    ensure_legacy_path()
    from core.ai_analytics.insights import top_categories_insights as _fn

    return _fn(df, logical_types, limit_cols=limit_cols)


def insights_detect_outliers(df, logical_types):
    ensure_legacy_path()
    from core.ai_analytics.insights import detect_numeric_outliers as _fn

    return _fn(df, logical_types)


def insights_compare_clinic_estado(df):
    ensure_legacy_path()
    from core.ai_analytics.insights import compare_clinic_estado as _fn

    return _fn(df)


def insights_compare_clinic_especialidad_ingreso(df):
    ensure_legacy_path()
    from core.ai_analytics.insights import compare_clinic_especialidad_ingreso as _fn

    return _fn(df)


def insights_compare_categorical_numeric(df, cat_col, num_col):
    ensure_legacy_path()
    from core.ai_analytics.insights import compare_categorical_numeric as _fn

    return _fn(df, cat_col, num_col)


def insights_pick_compare_pair(df, logical_types):
    ensure_legacy_path()
    from core.ai_analytics.insights import pick_compare_pair as _fn

    return _fn(df, logical_types)
