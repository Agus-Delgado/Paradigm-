"""KPIs operativos opcionales para el dataset demo de consultorio (capa desacoplada del core)."""

from __future__ import annotations

from typing import Any

import pandas as pd

# Columnas mínimas para mostrar el bloque de KPIs del consultorio
CLINIC_KPI_MIN_COLUMNS = frozenset(
    {
        "estado_turno",
        "especialidad",
        "ingreso_neto",
        "medio_pago",
        "cobertura_medica",
    }
)


def clinic_kpis_available(df: pd.DataFrame) -> bool:
    return CLINIC_KPI_MIN_COLUMNS.issubset(df.columns)


def compute_clinic_kpis(df: pd.DataFrame) -> dict[str, Any]:
    """
    Devuelve métricas de negocio simples. Solo llamar si clinic_kpis_available(df).
    """
    n = len(df)
    estado = df["estado_turno"].astype(str).str.strip().str.lower()
    counts = estado.value_counts()

    def pct(label: str) -> float:
        return float(counts.get(label, 0)) / float(n) * 100.0 if n else 0.0

    top_esp = (
        df["especialidad"].astype(str).value_counts().index[0]
        if n and df["especialidad"].notna().any()
        else "—"
    )

    ingreso = pd.to_numeric(df["ingreso_neto"], errors="coerce")
    ingreso_total = float(ingreso.sum(skipna=True))

    mp = df["medio_pago"].dropna()
    medio_frec = str(mp.astype(str).value_counts().index[0]) if len(mp) else "—"

    cob = df["cobertura_medica"].dropna()
    cob_frec = str(cob.astype(str).value_counts().index[0]) if len(cob) else "—"

    return {
        "n_turnos": n,
        "pct_asistido": pct("asistido"),
        "pct_cancelado": pct("cancelado"),
        "pct_ausente": pct("ausente"),
        "pct_reprogramado": pct("reprogramado"),
        "especialidad_mayor_volumen": top_esp,
        "ingreso_neto_total": ingreso_total,
        "medio_pago_frecuente": medio_frec,
        "cobertura_medica_frecuente": cob_frec,
    }
