"""Carga del mart SQLite, filtros, KPIs y promedios históricos para ML."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from app.config import BUILD_COMMANDS, REPO_ROOT

# Importar helpers ML del paquete paradigm (PYTHONPATH configurado en streamlit_app.py)
from paradigm.io.paths import DB_PATH
from paradigm.ml.dataset import load_eligible_appointments
from paradigm.ml.features import add_booking_calendar_features, add_historical_features

HISTORICAL_NUMERIC = [
    "patient_prior_appt_count",
    "patient_prior_no_show_count",
    "patient_prior_no_show_rate",
    "provider_prior_appt_count",
    "provider_prior_no_show_count",
    "provider_prior_no_show_rate",
]

QUERIES: dict[str, str] = {
    "appointments": "SELECT * FROM vw_appointment_base",
    "revenue_bridge": "SELECT * FROM vw_revenue_bridge",
    "billing": """
        SELECT f.*, bs.status_code AS billing_status_code
        FROM fact_billing_line f
        JOIN dim_billing_status bs ON f.billing_status_id = bs.billing_status_id
    """,
    "specialties": "SELECT specialty_id, specialty_name FROM dim_specialty ORDER BY specialty_id",
    "providers": "SELECT provider_id, provider_label FROM dim_provider ORDER BY provider_id",
    "channels": "SELECT booking_channel_id, channel_code, channel_name FROM dim_booking_channel ORDER BY booking_channel_id",
    "coverages": "SELECT coverage_id, coverage_name FROM dim_coverage ORDER BY coverage_id",
    "patients_meta": "SELECT DISTINCT age_band, sex FROM dim_patient ORDER BY age_band, sex",
}


@dataclass(frozen=True)
class FilterState:
    date_start: pd.Timestamp
    date_end: pd.Timestamp
    specialties: list[str]
    providers: list[str]
    channels: list[str]


@dataclass
class ExecutiveKpis:
    citas_total: int
    attended: int
    cancelled: int
    noshow: int
    no_show_rate: float | None
    cancellation_rate: float | None
    revenue: float
    billing_gap_count: int
    billing_gap_amount: float


def db_exists(db_path: Path = DB_PATH) -> bool:
    return db_path.is_file()


def ensure_db(db_path: Path = DB_PATH) -> bool:
    """Muestra error en Streamlit si falta la DB. Retorna True si existe."""
    if db_path.is_file():
        return True
    st.error("No se encontró el mart SQLite.")
    st.markdown(
        "Generá la base de datos ejecutando estos comandos desde la raíz del repo:"
    )
    st.code(BUILD_COMMANDS, language="bash")
    return False


@st.cache_data(show_spinner="Cargando mart SQLite…")
def load_mart_tables(db_path_str: str, db_mtime: float) -> dict[str, pd.DataFrame]:
    """Carga tablas/vistas principales. `db_mtime` invalida caché al regenerar."""
    _ = db_mtime
    db_path = Path(db_path_str)
    conn = sqlite3.connect(str(db_path))
    try:
        tables = {key: pd.read_sql_query(sql, conn) for key, sql in QUERIES.items()}
    finally:
        conn.close()

    apt = tables["appointments"]
    apt["appointment_date"] = pd.to_datetime(apt["appointment_date"])
    tables["appointments"] = apt

    rb = tables["revenue_bridge"]
    rb["appointment_date"] = pd.to_datetime(rb["appointment_date"])
    tables["revenue_bridge"] = rb

    billing = tables["billing"]
    billing["billing_date"] = pd.to_datetime(billing["billing_date"])
    tables["billing"] = billing

    return tables


@st.cache_data(show_spinner="Calculando promedios históricos…")
def load_historical_defaults(db_path_str: str, db_mtime: float) -> dict[str, float]:
    """Promedios reales de features históricas sobre citas elegibles (ATTENDED + NO_SHOW)."""
    _ = db_mtime
    df = load_eligible_appointments(Path(db_path_str))
    df = add_booking_calendar_features(df)
    df = add_historical_features(df)
    return {col: float(df[col].mean()) for col in HISTORICAL_NUMERIC}


def get_db_mtime(db_path: Path = DB_PATH) -> float:
    return db_path.stat().st_mtime if db_path.is_file() else 0.0


def apply_filters(tables: dict[str, pd.DataFrame], filters: FilterState) -> pd.DataFrame:
    """Filtra vw_appointment_base según estado del sidebar."""
    df = tables["appointments"].copy()
    mask = (
        (df["appointment_date"] >= filters.date_start)
        & (df["appointment_date"] <= filters.date_end)
    )
    if filters.specialties:
        mask &= df["specialty_name"].isin(filters.specialties)
    if filters.providers:
        mask &= df["provider_label"].isin(filters.providers)
    if filters.channels:
        mask &= df["channel_code"].isin(filters.channels)
    return df.loc[mask].copy()


def _bridge_for_filtered(
    filtered: pd.DataFrame, tables: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    ids = set(filtered["appointment_id"])
    rb = tables["revenue_bridge"]
    return rb[rb["appointment_id"].isin(ids)].copy()


def compute_kpis(
    filtered: pd.DataFrame, tables: dict[str, pd.DataFrame]
) -> ExecutiveKpis:
    """KPIs ejecutivos alineados a validate_executive_kpis.py."""
    total = len(filtered)
    attended = int((filtered["status_code"] == "ATTENDED").sum())
    cancelled = int((filtered["status_code"] == "CANCELLED").sum())
    noshow = int((filtered["status_code"] == "NO_SHOW").sum())
    denom_ns = attended + noshow
    no_show_rate = (noshow / denom_ns) if denom_ns else None
    cancellation_rate = (cancelled / total) if total else None

    apt_ids = set(filtered["appointment_id"])
    billing = tables["billing"]
    bill_filtered = billing[
        billing["appointment_id"].isin(apt_ids) & (billing["billing_status_code"] != "VOID")
    ]
    revenue = float(bill_filtered["line_amount"].sum()) if len(bill_filtered) else 0.0

    bridge = _bridge_for_filtered(filtered, tables)
    gap_rows = bridge[bridge["reconciliation_bucket"] == "ATTENDED_NO_BILLING"]
    gap_count = len(gap_rows)
    gap_amount = float(gap_rows["revenue_total_non_void"].sum()) if gap_count else 0.0

    return ExecutiveKpis(
        citas_total=total,
        attended=attended,
        cancelled=cancelled,
        noshow=noshow,
        no_show_rate=no_show_rate,
        cancellation_rate=cancellation_rate,
        revenue=revenue,
        billing_gap_count=gap_count,
        billing_gap_amount=gap_amount,
    )


def daily_trend(filtered: pd.DataFrame) -> pd.DataFrame:
    """Serie diaria: atendidas y tasa no-show."""
    if filtered.empty:
        return pd.DataFrame(columns=["appointment_date", "attended", "no_show_rate"])

    g = filtered.groupby("appointment_date", as_index=False).agg(
        attended=("status_code", lambda s: (s == "ATTENDED").sum()),
        noshow=("status_code", lambda s: (s == "NO_SHOW").sum()),
    )
    denom = g["attended"] + g["noshow"]
    g["no_show_rate"] = g["noshow"] / denom.replace(0, pd.NA)
    return g.sort_values("appointment_date")


def specialty_breakdown(filtered: pd.DataFrame) -> pd.DataFrame:
    """Conteos y tasa no-show por especialidad."""
    if filtered.empty:
        return pd.DataFrame(
            columns=["specialty_name", "attended", "noshow", "no_show_rate", "total"]
        )

    rows: list[dict[str, Any]] = []
    for name, grp in filtered.groupby("specialty_name", sort=True):
        attended = int((grp["status_code"] == "ATTENDED").sum())
        noshow = int((grp["status_code"] == "NO_SHOW").sum())
        denom = attended + noshow
        rows.append(
            {
                "specialty_name": name,
                "attended": attended,
                "noshow": noshow,
                "total": len(grp),
                "no_show_rate": (noshow / denom) if denom else None,
            }
        )
    return pd.DataFrame(rows).sort_values("attended", ascending=True)


def reconciliation_summary(
    filtered: pd.DataFrame, tables: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """Conteo por reconciliation_bucket (solo citas atendidas relevantes)."""
    bridge = _bridge_for_filtered(filtered, tables)
    attended_bridge = bridge[bridge["status_code"] == "ATTENDED"]
    if attended_bridge.empty:
        return pd.DataFrame(columns=["reconciliation_bucket", "count"])
    return (
        attended_bridge.groupby("reconciliation_bucket", as_index=False)
        .size()
        .rename(columns={"size": "count"})
        .sort_values("count", ascending=False)
    )


def attended_no_billing_detail(
    filtered: pd.DataFrame, tables: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """Detalle ATTENDED_NO_BILLING enriquecido con dimensiones."""
    bridge = _bridge_for_filtered(filtered, tables)
    gap = bridge[bridge["reconciliation_bucket"] == "ATTENDED_NO_BILLING"].copy()
    if gap.empty:
        return gap

    dims = filtered[
        ["appointment_id", "specialty_name", "provider_label", "channel_code"]
    ].drop_duplicates()
    return gap.merge(dims, on="appointment_id", how="left").sort_values("appointment_date")


def monthly_attended_vs_billed(
    filtered: pd.DataFrame, tables: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """Comparativa mensual: citas atendidas vs monto facturado (por cita)."""
    attended = filtered[filtered["status_code"] == "ATTENDED"].copy()
    if attended.empty:
        return pd.DataFrame(columns=["year_month", "attended_count", "billed_amount"])

    attended["year_month"] = attended["appointment_date"].dt.to_period("M").astype(str)
    counts = attended.groupby("year_month", as_index=False).size().rename(columns={"size": "attended_count"})

    apt_ids = set(attended["appointment_id"])
    billing = tables["billing"]
    bill = billing[
        billing["appointment_id"].isin(apt_ids) & (billing["billing_status_code"] != "VOID")
    ].copy()
    if bill.empty:
        counts["billed_amount"] = 0.0
        return counts

    bill = bill.merge(
        attended[["appointment_id", "year_month"]].drop_duplicates(),
        on="appointment_id",
        how="inner",
    )
    amounts = bill.groupby("year_month", as_index=False)["line_amount"].sum().rename(
        columns={"line_amount": "billed_amount"}
    )
    return counts.merge(amounts, on="year_month", how="left").fillna({"billed_amount": 0.0})


def run_regenerate_pipeline(include_train: bool = False) -> tuple[bool, str]:
    """Ejecuta scripts de regeneración vía subprocess."""
    python = sys.executable
    steps = [
        [python, str(REPO_ROOT / "scripts" / "generate_paradigm_v2_synthetic.py")],
        [python, str(REPO_ROOT / "scripts" / "build_sqlite_mart.py")],
    ]
    if include_train:
        steps.append([python, str(REPO_ROOT / "scripts" / "train_no_show.py")])

    logs: list[str] = []
    for cmd in steps:
        logs.append(f"$ {' '.join(cmd)}\n")
        result = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout:
            logs.append(result.stdout)
        if result.stderr:
            logs.append(result.stderr)
        if result.returncode != 0:
            logs.append(f"\n[ERROR] exit code {result.returncode}\n")
            return False, "".join(logs)
    return True, "".join(logs)


def mart_appointments_to_analyst_df(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """DataFrame plano de citas para el analista conversacional."""
    return tables["appointments"].copy()


def prepare_dataset_context(
    df: pd.DataFrame,
    *,
    source: str,
    source_label: str,
):
    """Infiere schema, perfila y detecta dominio."""
    from app.conversational.domain import detect_domain
    from app.conversational.legacy_bridge import (
        build_findings,
        build_profile,
        infer_logical_types,
    )
    from app.conversational.session_utils import make_dataset_key
    from app.conversational.types import DatasetContext

    logical_types = infer_logical_types(df)
    profile = build_profile(df, logical_types)
    findings = build_findings(df, profile, logical_types)
    domain = detect_domain(df, logical_types)
    dataset_key = make_dataset_key(source, source_label, df.shape)
    return DatasetContext(
        df=df,
        logical_types=logical_types,
        profile=profile,
        findings=findings,
        domain=domain,
        dataset_key=dataset_key,
        source_label=source_label,
    )


def load_analyst_csv(uploaded) -> tuple[pd.DataFrame | None, str | None]:
    """Carga CSV/XLSX para el flujo analista."""
    from app.conversational.legacy_bridge import load_uploaded_file

    return load_uploaded_file(uploaded)


def load_analyst_demo_csv() -> tuple[pd.DataFrame | None, str | None]:
    """Dataset demo consultorio (compatible no-shows legacy)."""
    from app.conversational.legacy_bridge import DEMO_CLINIC_CSV, load_csv_path

    return load_csv_path(DEMO_CLINIC_CSV)
