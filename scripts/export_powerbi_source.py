"""
Exporta tablas/vistas del mart SQLite a CSV en bi/powerbi/source_csv/
para importación en Power BI Desktop (MVP ejecutivo).

Requiere: python scripts/build_sqlite_mart.py

Uso:
    python scripts/export_powerbi_source.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "processed" / "paradigm_mart.db"
OUT = ROOT / "bi" / "powerbi" / "source_csv"

# Nombres de archivo = nombres de tabla recomendados en Power BI (sin prefijo vw_)
EXPORTS: list[tuple[str, str]] = [
    ("SELECT * FROM vw_appointment_base", "AppointmentBase.csv"),
    ("SELECT * FROM fact_billing_line", "BillingLine.csv"),
    ("SELECT * FROM dim_billing_status", "DimBillingStatus.csv"),
    ("SELECT * FROM dim_date", "DimDate.csv"),
    ("SELECT * FROM vw_daily_kpis", "DailyKpis.csv"),
    ("SELECT * FROM vw_kpis_by_specialty", "KpiBySpecialty.csv"),
    ("SELECT * FROM vw_revenue_bridge", "RevenueBridge.csv"),
]


def main() -> None:
    if not DB.is_file():
        raise SystemExit(f"No existe {DB}. Ejecutá: python scripts/build_sqlite_mart.py")
    OUT.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    try:
        for sql, fname in EXPORTS:
            df = pd.read_sql_query(sql, conn)
            path = OUT / fname
            df.to_csv(path, index=False, encoding="utf-8-sig")
            print(f"OK {fname} ({len(df)} filas)")
    finally:
        conn.close()
    print(f"Salida: {OUT}")


if __name__ == "__main__":
    main()
