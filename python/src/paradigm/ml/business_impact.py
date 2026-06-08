"""
Simulación de impacto operativo: priorización por score y revenue estimado (ARS).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from paradigm.ml.evaluate import top_fraction_capture

# Fallback cuando el mart no tiene facturación utilizable (ARS por cita demo).
DEFAULT_AVG_REVENUE_ARS: float = 12_500.0


def _revenue_from_billing(conn: sqlite3.Connection) -> float | None:
    """Promedio de líneas facturadas (no VOID) por cita con al menos una línea."""
    q = """
    SELECT
      fa.appointment_id,
      SUM(fbl.line_amount) AS revenue
    FROM fact_appointment fa
    JOIN fact_billing_line fbl ON fbl.appointment_id = fa.appointment_id
    JOIN dim_billing_status bs ON fbl.billing_status_id = bs.billing_status_id
    WHERE bs.status_code != 'VOID'
    GROUP BY fa.appointment_id
    HAVING revenue > 0
    """
    df = pd.read_sql_query(q, conn)
    if df.empty or df["revenue"].sum() <= 0:
        return None
    return float(df["revenue"].mean())


def _revenue_from_bridge(conn: sqlite3.Connection) -> float | None:
    """Segundo intento: puente de revenue por cita atendida."""
    q = """
    SELECT appointment_id, revenue_total_non_void
    FROM vw_revenue_bridge
    WHERE revenue_total_non_void > 0
    """
    try:
        df = pd.read_sql_query(q, conn)
    except Exception:
        return None
    if df.empty:
        return None
    return float(df["revenue_total_non_void"].mean())


def avg_revenue_per_appointment(
    db_path: Path,
    fallback: float = DEFAULT_AVG_REVENUE_ARS,
) -> tuple[float, str]:
    """
    Valor promedio por cita (ARS) con fallback en cascada:
    1) fact_billing_line agregada por cita
    2) vw_revenue_bridge
    3) constante DEFAULT_AVG_REVENUE_ARS
    """
    if not db_path.is_file():
        return fallback, "fallback_constant (db missing)"

    conn = sqlite3.connect(str(db_path))
    try:
        val = _revenue_from_billing(conn)
        if val is not None and val > 0:
            return val, "fact_billing_line"

        val = _revenue_from_bridge(conn)
        if val is not None and val > 0:
            return val, "vw_revenue_bridge"
    finally:
        conn.close()

    return fallback, "fallback_constant"


def simulate_prioritization_impact(
    y_true: np.ndarray | pd.Series,
    y_score: np.ndarray,
    top_fraction: float,
    avg_revenue_ars: float,
    reassignment_rate: float = 1.0,
) -> dict[str, Any]:
    """
    Dado un top X% por score descendente, estima citas priorizadas,
    slots liberados (no-shows evitados × tasa de reasignación) e ingreso recuperado.
    """
    fraction = float(np.clip(top_fraction, 0.01, 1.0))
    y = np.asarray(y_true).astype(int)
    s = np.asarray(y_score, dtype=float)
    capture = top_fraction_capture(y, s, fraction=fraction)

    n_prioritized = int(capture["k_top"])
    no_shows_in_top = int(capture["positives_in_top_fraction"])
    baseline_no_shows = int(capture["positives_total"])
    slots_liberated = float(no_shows_in_top * reassignment_rate)
    revenue_recovered = slots_liberated * avg_revenue_ars
    baseline_revenue_at_risk = baseline_no_shows * avg_revenue_ars

    comparison = pd.DataFrame(
        [
            {
                "scenario": "Baseline (sin priorizar)",
                "metric": "Ingreso en riesgo (no-shows)",
                "value_ars": baseline_revenue_at_risk,
            },
            {
                "scenario": f"Top {int(round(fraction * 100))}% priorizado",
                "metric": "Ingreso recuperado estimado",
                "value_ars": revenue_recovered,
            },
        ]
    )

    return {
        "top_fraction": fraction,
        "appointments_prioritized": n_prioritized,
        "no_shows_in_prioritized": no_shows_in_top,
        "slots_liberated_est": slots_liberated,
        "revenue_recovered_ars": revenue_recovered,
        "baseline_no_shows": baseline_no_shows,
        "baseline_revenue_at_risk_ars": baseline_revenue_at_risk,
        "capture_rate": capture["capture_rate"],
        "avg_revenue_ars": avg_revenue_ars,
        "reassignment_rate": reassignment_rate,
        "comparison_df": comparison,
    }


def simulate_from_shap_bundle(
    db_path: Path,
    bundle: dict[str, Any],
    top_fraction: float,
    reassignment_rate: float = 1.0,
) -> dict[str, Any]:
    """Simula impacto usando hold-out guardado en el bundle SHAP."""
    meta = bundle["test_meta"]
    y_true = meta["y_true"].values
    y_score = meta["predicted_proba"].values
    avg_rev, source = avg_revenue_per_appointment(db_path)
    out = simulate_prioritization_impact(
        y_true=y_true,
        y_score=y_score,
        top_fraction=top_fraction,
        avg_revenue_ars=avg_rev,
        reassignment_rate=reassignment_rate,
    )
    out["avg_revenue_source"] = source
    return out
