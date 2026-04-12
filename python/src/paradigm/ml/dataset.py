"""
Carga citas elegibles para el modelo de no-show: solo ATTENDED y NO_SHOW
(universo alineado a docs/metric_definitions.md para la tasa de no-show).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

LOAD_SQL = """
SELECT
  fa.appointment_id,
  fa.patient_id,
  fa.provider_id,
  fa.specialty_id,
  fa.coverage_id,
  fa.booking_channel_id,
  fa.appointment_date,
  fa.appointment_start,
  fa.booking_date,
  fa.booking_ts,
  st.status_code,
  p.age_band,
  p.sex
FROM fact_appointment fa
JOIN dim_appointment_status st ON fa.appointment_status_id = st.appointment_status_id
JOIN dim_patient p ON fa.patient_id = p.patient_id
WHERE st.status_code IN ('ATTENDED', 'NO_SHOW')
"""


def load_eligible_appointments(db_path: Path) -> pd.DataFrame:
    """Devuelve un DataFrame por cita con etiqueta operativa posible (asistida / no-show)."""
    if not db_path.is_file():
        raise FileNotFoundError(f"No existe la base: {db_path}")
    conn = sqlite3.connect(str(db_path))
    try:
        df = pd.read_sql_query(LOAD_SQL, conn)
    finally:
        conn.close()
    df["appointment_date"] = pd.to_datetime(df["appointment_date"])
    df["booking_date"] = pd.to_datetime(df["booking_date"])
    df["target_no_show"] = (df["status_code"] == "NO_SHOW").astype(int)
    return df
