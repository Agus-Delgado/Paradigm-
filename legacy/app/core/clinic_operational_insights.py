"""Hallazgos operativos opcionales para el caso consultorio (sin acoplar a findings.py genérico)."""

from __future__ import annotations

import pandas as pd

from core.findings import Finding

# Columnas mínimas para generar insights operativos
CLINIC_INSIGHT_MIN_COLUMNS = frozenset(
    {
        "estado_turno",
        "especialidad",
        "franja_horaria",
        "cobertura_medica",
        "ingreso_neto",
    }
)

PRIORITY_OP = 5
MAX_INSIGHTS = 5


def clinic_operational_insights_available(df: pd.DataFrame) -> bool:
    return CLINIC_INSIGHT_MIN_COLUMNS.issubset(df.columns)


def build_clinic_operational_insights(df: pd.DataFrame) -> list[Finding]:
    """Hasta 5 mensajes informativos sobre el subconjunto cargado (dataset completo en Paradigm)."""
    if not clinic_operational_insights_available(df) or len(df) == 0:
        return []

    out: list[Finding] = []
    n = len(df)

    # 1) Distribución de estado_turno (top 3)
    est = df["estado_turno"].astype(str).str.strip().str.lower()
    vc = est.value_counts()
    top3 = vc.head(3)
    parts = [f"{idx}: {100.0 * v / n:.1f}%" for idx, v in top3.items()]
    out.append(
        Finding(
            PRIORITY_OP,
            "info",
            "Distribución de estados de turno (top): " + "; ".join(parts) + ".",
        )
    )

    # 2) Especialidad con mayor volumen
    esp = df["especialidad"].astype(str)
    top_esp = esp.value_counts().index[0]
    share = float(esp.value_counts().iloc[0]) / float(n) * 100.0
    out.append(
        Finding(
            PRIORITY_OP + 1,
            "info",
            f"Especialidad con mayor volumen: «{top_esp}» ({share:.1f}% de los turnos).",
        )
    )

    # 3) Franja horaria con mayor demanda
    fr = df["franja_horaria"].astype(str)
    top_fr = fr.value_counts().index[0]
    share_fr = float(fr.value_counts().iloc[0]) / float(n) * 100.0
    out.append(
        Finding(
            PRIORITY_OP + 2,
            "info",
            f"Mayor demanda en franja «{top_fr}» ({share_fr:.1f}% de los turnos).",
        )
    )

    # 4) Cobertura médica predominante (paciente)
    cob = df["cobertura_medica"].dropna().astype(str)
    if len(cob):
        top_cob = cob.value_counts().index[0]
        share_c = float(cob.value_counts().iloc[0]) / float(len(cob)) * 100.0
        out.append(
            Finding(
                PRIORITY_OP + 3,
                "info",
                f"Cobertura médica más frecuente en pacientes: «{top_cob}» (~{share_c:.1f}% de filas con dato).",
            )
        )

    # 5) Concentración de ingreso_neto por especialidad (turnos con facturación)
    ing = pd.to_numeric(df["ingreso_neto"], errors="coerce")
    mask_bill = ing.notna() & (ing > 0)
    if int(mask_bill.sum()) > 0:
        sub = df.loc[mask_bill, ["especialidad"]].copy()
        sub["_ing"] = ing.loc[mask_bill].values
        by_esp = sub.groupby("especialidad", dropna=False)["_ing"].sum().sort_values(ascending=False)
        top_e = by_esp.index[0]
        share_i = float(by_esp.iloc[0]) / float(by_esp.sum()) * 100.0
        out.append(
            Finding(
                PRIORITY_OP + 4,
                "info",
                f"Concentración de ingreso neto facturado: «{top_e}» concentra ~{share_i:.1f}% del total.",
            )
        )

    out.sort(key=lambda f: (f.priority, f.severity))
    return out[:MAX_INSIGHTS]
