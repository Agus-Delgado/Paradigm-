"""Detección heurística de dominio de negocio a partir del schema."""

from __future__ import annotations

import re

import pandas as pd

from app.conversational.legacy_bridge import clinic_kpis_available
from app.conversational.types import Domain

_CLINIC_COLUMN_SIGNALS = frozenset(
    {
        "estado_turno",
        "especialidad",
        "ingreso_neto",
        "medio_pago",
        "cobertura_medica",
        "fecha_turno",
        "paciente_id",
    }
)

_MART_COLUMN_SIGNALS = frozenset(
    {
        "status_code",
        "appointment_date",
        "specialty_name",
        "provider_label",
        "channel_code",
        "appointment_id",
    }
)

_OPERATIONS_KEYWORDS = (
    "planta",
    "linea",
    "línea",
    "defecto",
    "defect",
    "produccion",
    "producción",
    "orden",
    "turno",
    "ciclo",
    "unidades",
    "oee",
    "scrap",
    "manufactura",
    "operaciones",
)

_FINANCE_KEYWORDS = (
    "ingreso",
    "costo",
    "coste",
    "margen",
    "presupuesto",
    "budget",
    "factura",
    "billing",
    "revenue",
    "impuesto",
    "iva",
    "deuda",
    "pago",
    "saldo",
    "contabil",
    "contad",
    "financ",
    "neto",
    "bruto",
    "ebitda",
    "gasto",
    "expense",
    "profit",
    "loss",
)


def _normalize_col(name: str) -> str:
    return re.sub(r"[\s_\-]+", " ", name.strip().lower())


def _column_matches_keywords(col: str, keywords: tuple[str, ...]) -> bool:
    norm = _normalize_col(col)
    return any(kw in norm for kw in keywords)


def _finance_score(columns: list[str], logical_types: dict[str, str]) -> int:
    score = 0
    numeric_finance = 0
    for col in columns:
        norm = _normalize_col(col)
        if _column_matches_keywords(col, _FINANCE_KEYWORDS):
            score += 2
            if logical_types.get(col) == "numeric":
                numeric_finance += 1
        if any(k in norm for k in ("monto", "amount", "total", "importe")):
            score += 1
    if numeric_finance >= 2:
        score += 3
    return score


def _clinic_score(columns: list[str]) -> int:
    col_set = {c.lower() for c in columns}
    hits = len(_CLINIC_COLUMN_SIGNALS & col_set)
    if "estado_turno" in col_set:
        hits += 2
    return hits


def _operations_score(columns: list[str], logical_types: dict[str, str]) -> int:
    score = 0
    col_set = {c.lower() for c in columns}
    for col in columns:
        if _column_matches_keywords(col, _OPERATIONS_KEYWORDS):
            score += 2
    if "planta" in col_set and "defectos" in col_set:
        score += 4
    if "tiempo_ciclo_min" in col_set or any("ciclo" in c for c in col_set):
        score += 2
    if logical_types.get("defectos") == "numeric" or "defectos" in col_set:
        score += 1
    return score


def _mart_score(columns: list[str]) -> int:
    col_set = {c.lower() for c in columns}
    hits = len(_MART_COLUMN_SIGNALS & col_set)
    if "status_code" in col_set and "appointment_date" in col_set:
        hits += 3
    return hits


def detect_domain(df: pd.DataFrame, logical_types: dict[str, str]) -> Domain:
    """Clasifica el dataset en healthcare_clinic, healthcare_mart, finance o generic."""
    if df is None or df.empty or df.shape[1] == 0:
        return "generic"

    columns = list(df.columns)

    if clinic_kpis_available(df):
        return "healthcare_clinic"

    clinic_hits = _clinic_score(columns)
    mart_hits = _mart_score(columns)
    finance_hits = _finance_score(columns, logical_types)
    operations_hits = _operations_score(columns, logical_types)

    if mart_hits >= 4 and mart_hits >= clinic_hits:
        return "healthcare_mart"

    if clinic_hits >= 3:
        return "healthcare_clinic"

    if operations_hits >= 5 and operations_hits >= finance_hits:
        return "operations"

    if finance_hits >= 4:
        return "finance"

    if operations_hits >= 4:
        return "operations"

    if clinic_hits >= 2 and clinic_hits > finance_hits:
        return "healthcare_clinic"

    return "generic"


def domain_label_es(domain: Domain) -> str:
    return {
        "healthcare_clinic": "Salud / consultorio ambulatorio",
        "healthcare_mart": "Operaciones clínicas (mart)",
        "finance": "Finanzas / contaduría",
        "operations": "Operaciones / manufactura",
        "generic": "Análisis general",
    }[domain]


_VOCABULARY_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("facturación", ("factura", "billing", "invoice", "monto", "importe", "cobro", "cliente", "customer")),
    ("contabilidad", ("contabil", "contad", "cuenta", "presupuesto", "budget", "iva", "impuesto", "saldo")),
    ("finanzas", ("ingreso", "costo", "margen", "ebitda", "gasto", "expense", "revenue", "profit")),
    ("tickets", ("ticket", "incident", "issue", "case", "soporte", "support")),
    ("tecnología", ("severidad", "severity", "equipo", "team", "squad", "backend", "frontend", "bug", "sla")),
    ("salud", ("paciente", "turno", "especialidad", "medico", "clinic", "appointment")),
    ("operaciones", ("planta", "linea", "defecto", "produccion", "manufactura", "orden", "scrap")),
    ("logística", ("envio", "shipping", "delivery", "almacen", "warehouse", "stock")),
)


def extract_column_vocabulary(columns: list[str]) -> tuple[str, ...]:
    """Temas inferidos de nombres de columnas para adaptar tono en dominio generic."""
    if not columns:
        return ()
    joined = " ".join(_normalize_col(c) for c in columns)
    found: list[tuple[int, str]] = []
    for label, keywords in _VOCABULARY_GROUPS:
        hits = sum(1 for kw in keywords if kw in joined)
        if hits > 0:
            found.append((hits, label))
    found.sort(key=lambda x: (-x[0], x[1]))
    return tuple(label for _, label in found[:4])
